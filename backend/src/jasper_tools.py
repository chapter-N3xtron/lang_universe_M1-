import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import httpx
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from src.visual_models import (
    ConceptMapArtifact,
    ConceptMapPayload,
    DrawConceptMapInput,
    EvidenceSource,
)

TODOS_FILE = os.getenv(
    "TODOS_FILE",
    str(Path(__file__).resolve().parent.parent.parent / "todos.json"),
)

BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".avif",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".flv",
        ".wav",
        ".ogg",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".wasm",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".pyc",
        ".pyo",
        ".pyd",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".o",
        ".a",
        ".lib",
        ".obj",
        ".class",
        ".iso",
        ".img",
    }
)

MAX_FILE_SIZE = 100 * 1024
SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        "credentials",
        "credentials.json",
        "secrets.json",
    }
)
SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})
_AGENT_WORKSPACE: ContextVar[str | None] = ContextVar(
    "jasper_agent_workspace", default=None
)
_EVIDENCE_REGISTRY: ContextVar[dict[str, EvidenceSource] | None] = ContextVar(
    "jasper_visual_evidence", default=None
)


@contextmanager
def agent_workspace(path: str | None) -> Iterator[None]:
    """Scope Jasper's workspace to one run without mutating process globals."""

    token = _AGENT_WORKSPACE.set(path)
    try:
        yield
    finally:
        _AGENT_WORKSPACE.reset(token)


def _register_evidence(
    *, kind: str, locator: str, title: str, content: str, source_id: str | None = None
) -> EvidenceSource | None:
    registry = _EVIDENCE_REGISTRY.get()
    if registry is None:
        return None
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if source_id is None:
        prefix = "repo" if kind == "repo_file" else "web"
        identity = hashlib.sha256(
            f"{kind}\n{locator}\n{content_hash}".encode()
        ).hexdigest()[:16]
        source_id = f"{prefix}-{identity}"
    source = EvidenceSource(
        id=source_id,
        kind=kind,
        locator=locator,
        title=title,
        content_sha256=content_hash,
    )
    registry[source.id] = source
    return source


def _evidence_header(source: EvidenceSource | None) -> str:
    if source is None:
        return ""
    return (
        f'[Evidence id="{source.id}" kind="{source.kind}" locator="{source.locator}"]\n'
    )


@contextmanager
def agent_evidence(user_text: str | None) -> Iterator[None]:
    """Scope authoritative visual evidence to one Jasper run."""

    token = _EVIDENCE_REGISTRY.set({})
    try:
        if user_text and user_text.strip():
            _register_evidence(
                kind="user_input",
                locator="current-user-message",
                title="Current user request",
                content=user_text.strip(),
                source_id="user-input",
            )
        yield
    finally:
        _EVIDENCE_REGISTRY.reset(token)


@tool
def list_todos() -> str:
    """Read the project's todo list and return current task status, completion status, and model attribution."""
    try:
        with open(TODOS_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return "Could not read todos.json — file not found or invalid JSON."

    sections = data.get("sections", [])
    if not sections:
        return "No todos tracked."

    lines = []
    for section in sections:
        model = section.get("planned_by_model", "unknown")
        lines.append(f"## {section['title']} (planned by {model})")
        for t in section.get("todos", []):
            mark = {"pending": "○", "in_progress": "◉", "completed": "✓"}.get(
                t["status"], "○"
            )
            model_tag = (
                f" [done by {t['completed_by_model']}]"
                if t.get("completed_by_model")
                else ""
            )
            lines.append(f"  {mark} {t['content']}{model_tag}")
    result = "\n".join(lines)
    source = _register_evidence(
        kind="repo_file",
        locator="todos.json",
        title="Project todo list",
        content=result,
    )
    return _evidence_header(source) + result


@tool("read_repository_file")
def read_file(file_path: str) -> str:
    """Read a repository file and register it as evidence for grounded visuals.

    Security: path traversal and symlink attacks are blocked.
    Binary files and files over 100KB are rejected.
    """
    workspace = _AGENT_WORKSPACE.get() or os.getenv("AGENT_WORKSPACE", "")
    if not workspace:
        return "Error: AGENT_WORKSPACE environment variable is not set."

    workspace_path = Path(workspace).resolve()
    resolved = Path(file_path).expanduser()
    if not resolved.is_absolute():
        resolved = workspace_path / resolved
    resolved = resolved.resolve()

    try:
        resolved.relative_to(workspace_path)
    except ValueError:
        return "Error: Access denied — path is outside the workspace directory."

    if not resolved.exists():
        return f"Error: File not found: {file_path}"
    if not resolved.is_file():
        return f"Error: Not a file: {file_path}"

    if (
        resolved.name.lower() in SENSITIVE_NAMES
        or resolved.suffix.lower() in SENSITIVE_SUFFIXES
        or ".git" in resolved.parts
    ):
        return "Error: Access denied — sensitive files cannot be read by Jasper."

    ext = resolved.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return f"Error: Cannot read binary file: {file_path}"

    try:
        size = resolved.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"Error: File too large ({size} bytes). Maximum allowed: 100KB."
        text = resolved.read_text(encoding="utf-8", errors="replace")
        relative = resolved.relative_to(workspace_path).as_posix()
        source = _register_evidence(
            kind="repo_file",
            locator=relative,
            title=relative,
            content=text,
        )
        return _evidence_header(source) + text
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic using Tavily. Returns up to 5 results with titles, snippets, and URLs."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return (
            "Tavily search is not configured. "
            "Set the TAVILY_API_KEY environment variable to enable web search. "
            "Get a free key at https://app.tavily.com"
        )
    try:
        client = TavilySearch(max_results=5)
        result = client.invoke({"query": query})
        results = result.get("results", []) if isinstance(result, dict) else []
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            evidence_text = f"{title}\n{url}\n{content}"
            source = _register_evidence(
                kind="web_url",
                locator=url,
                title=title,
                content=evidence_text,
            )
            evidence_line = f"   Evidence: {source.id}\n" if source is not None else ""
            lines.append(
                f"{i}. {title}\n   URL: {url}\n{evidence_line}   {content[:300]}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"


@tool
def read_url(url: str) -> str:
    """Read and extract the content of a web page at the given URL. Returns the page content in markdown format."""
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        response = httpx.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/markdown"},
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        text = response.text
        if len(text) > 50000:
            text = text[:50000] + "\n\n[truncated at 50,000 characters]"
        source = _register_evidence(
            kind="web_url",
            locator=url,
            title=url,
            content=text,
        )
        return _evidence_header(source) + text
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code} when reading URL"
    except httpx.TimeoutException:
        return "Request timed out when reading URL"
    except Exception as e:
        return f"Failed to read URL: {e}"


@tool(args_schema=DrawConceptMapInput)
def draw_concept_map(
    title: str,
    alt_text: str,
    grounding_kind: str,
    nodes: list,
    narration_order: list,
    edges: list | None = None,
    direction: str = "left_to_right",
) -> dict:
    """Create a validated concept map when a visual would materially aid understanding.

    Every node and edge must cite evidence IDs returned by read_file, web_search,
    read_url, or the current user-input evidence. The current user message has the
    stable evidence ID "user-input" and may support only claims explicitly supplied
    by the user. Repository maps use
    grounding_kind="repo" and claim_status="observed" or "inferred". Research maps
    use grounding_kind="web" and claim_status="researched" or "inferred". Processes
    supplied by the user use "user_defined"; future designs use "proposed". Never
    present a proposal as observed implementation. The browser owns presentation.
    """

    validated = DrawConceptMapInput.model_validate(
        {
            "title": title,
            "alt_text": alt_text,
            "grounding_kind": grounding_kind,
            "nodes": nodes,
            "edges": edges or [],
            "narration_order": narration_order,
            "direction": direction,
        }
    )
    registry = _EVIDENCE_REGISTRY.get()
    if registry is None:
        raise ValueError("Visual evidence session is unavailable")
    referenced = {
        ref
        for item in [*validated.nodes, *validated.edges]
        for ref in item.evidence_refs
    }
    unknown = referenced - registry.keys()
    if unknown:
        raise ValueError(
            "Concept map cites evidence that was not returned by a trusted tool in "
            f"this run: {', '.join(sorted(unknown))}"
        )
    sources = [registry[source_id] for source_id in sorted(referenced)]
    artifact = ConceptMapArtifact(
        title=validated.title,
        alt_text=validated.alt_text,
        payload=ConceptMapPayload(
            grounding_kind=validated.grounding_kind,
            sources=sources,
            nodes=validated.nodes,
            edges=validated.edges,
            narration_order=validated.narration_order,
            direction=validated.direction,
        ),
    )
    return artifact.model_dump(mode="json")
