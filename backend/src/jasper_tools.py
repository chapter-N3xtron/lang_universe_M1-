import json
import os
from pathlib import Path

import httpx
from langchain_core.tools import tool

from langchain_tavily import TavilySearch

TODOS_FILE = os.getenv(
    "TODOS_FILE",
    str(Path(__file__).resolve().parent.parent.parent / "todos.json"),
)

BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".avif",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".pyd",
    ".woff", ".woff2", ".ttf", ".eot",
    ".o", ".a", ".lib", ".obj", ".class",
    ".iso", ".img",
})

MAX_FILE_SIZE = 100 * 1024


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
            mark = {"pending": "○", "in_progress": "◉", "completed": "✓"}.get(t["status"], "○")
            model_tag = f" [done by {t['completed_by_model']}]" if t.get("completed_by_model") else ""
            lines.append(f"  {mark} {t['content']}{model_tag}")
    return "\n".join(lines)


@tool
def read_file(file_path: str) -> str:
    """Read a file from the workspace directory and return its contents as text.

    Security: path traversal and symlink attacks are blocked.
    Binary files and files over 100KB are rejected.
    """
    workspace = os.getenv("OPENCODE_WORKSPACE", "")
    if not workspace:
        return "Error: OPENCODE_WORKSPACE environment variable is not set."

    workspace_path = Path(workspace).resolve()
    resolved = Path(file_path).expanduser()
    if not resolved.is_absolute():
        resolved = workspace_path / resolved
    resolved = resolved.resolve()

    try:
        resolved.relative_to(workspace_path)
    except ValueError:
        return f"Error: Access denied — path is outside the workspace directory."

    if not resolved.exists():
        return f"Error: File not found: {file_path}"
    if not resolved.is_file():
        return f"Error: Not a file: {file_path}"

    ext = resolved.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return f"Error: Cannot read binary file: {file_path}"

    try:
        size = resolved.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"Error: File too large ({size} bytes). Maximum allowed: 100KB."
        text = resolved.read_text(encoding="utf-8", errors="replace")
        return text
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
            lines.append(f"{i}. {title}\n   URL: {url}\n   {content[:300]}")
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
        return text
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code} when reading URL"
    except httpx.TimeoutException:
        return "Request timed out when reading URL"
    except Exception as e:
        return f"Failed to read URL: {e}"
