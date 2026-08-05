"""Durable, bounded Research evidence stored through the LangGraph Store."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.jasper_tools import (
    BINARY_EXTENSIONS,
    MAX_FILE_SIZE,
    SENSITIVE_NAMES,
    SENSITIVE_SUFFIXES,
)
from src.jasper_tools import (
    read_url as _read_url,
)
from src.jasper_tools import (
    web_search as _web_search,
)

MAX_EVIDENCE_CHARS = 50_000


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _identity(kind: str, locator: str, content: str) -> tuple[str, str]:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    digest = hashlib.sha256(f"{kind}\n{locator}\n{content_hash}".encode()).hexdigest()[
        :20
    ]
    return f"source-{digest}", content_hash


def _state_value(runtime: ToolRuntime, key: str, default: str = "") -> str:
    value = runtime.state.get(key, default)
    return value if isinstance(value, str) else default


def save_evidence(
    runtime: ToolRuntime,
    *,
    kind: str,
    locator: str,
    title: str,
    content: str,
    query: str = "",
    segments: list[dict[str, Any]] | None = None,
    truncated: bool = False,
) -> dict[str, Any]:
    """Save one immutable body and its session-specific source metadata."""

    bounded = content[:MAX_EVIDENCE_CHARS]
    was_truncated = truncated or len(content) > len(bounded)
    source_id, content_hash = _identity(kind, locator, bounded)
    retrieved_at = _now()
    reference = {
        "id": source_id,
        "stable_evidence_id": source_id,
        "version": content_hash[:12],
        "kind": kind,
        "locator": locator,
        "original_title": title,
        "display_name": title,
        "query": query,
        "retrieved_at": retrieved_at,
        "content_sha256": content_hash,
        "truncated": was_truncated,
        "segments": segments or [],
    }
    if runtime.store is not None:
        owner = _state_value(runtime, "user_identity", "anonymous") or "anonymous"
        thread = _state_value(runtime, "thread_identity")
        runtime.store.put(
            (owner, "research-evidence"),
            source_id,
            {
                **reference,
                "content": bounded,
            },
            index=False,
        )
        if thread:
            existing = runtime.store.get((owner, "session-sources", thread), source_id)
            session_value = dict(existing.value) if existing else reference
            runtime.store.put(
                (owner, "session-sources", thread),
                source_id,
                session_value,
                index=False,
            )
    return reference


def _tool_result(
    runtime: ToolRuntime, text: str, refs: list[dict[str, Any]]
) -> Command:
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=text, tool_call_id=runtime.tool_call_id or "research"
                )
            ],
            "session_evidence": refs,
        }
    )


@tool("web_search")
def research_web_search(query: str, runtime: ToolRuntime) -> Command:
    """Search the web and save each returned, unopened result as snippet-only evidence."""

    result = _web_search.invoke({"query": query})
    refs: list[dict[str, Any]] = []
    for block in re.split(r"\n\n(?=\d+\.)", result):
        title_match = re.match(r"\d+\.\s*(.+)", block)
        url_match = re.search(r"^\s*URL:\s*(https?://\S+)", block, re.MULTILINE)
        if not title_match or not url_match:
            continue
        refs.append(
            save_evidence(
                runtime,
                kind="web_snippet",
                locator=url_match.group(1),
                title=title_match.group(1).strip(),
                content=block,
                query=query,
            )
        )
    headers = "\n".join(
        f'[Evidence id="{ref["id"]}" kind="web_snippet" locator="{ref["locator"]}"]'
        for ref in refs
    )
    return _tool_result(runtime, f"{headers}\n{result}".strip(), refs)


@tool("read_url")
def research_read_url(url: str, runtime: ToolRuntime) -> Command:
    """Read one explicitly selected web page and save its bounded full text."""

    result = _read_url.invoke({"url": url})
    if result.startswith(("Error:", "HTTP error", "Request timed out", "Failed")):
        return _tool_result(runtime, result, [])
    content = re.sub(r"^\[Evidence[^\n]+\]\n", "", result)
    ref = save_evidence(
        runtime,
        kind="web_url",
        locator=url,
        title=url,
        content=content,
        truncated="[truncated at 50,000 characters]" in content,
    )
    return _tool_result(
        runtime,
        f'[Evidence id="{ref["id"]}" kind="web_url" locator="{url}"]\n{content}',
        [ref],
    )


@tool
def ingest_uploaded_sources(runtime: ToolRuntime) -> Command:
    """Save supported text already extracted from files explicitly uploaded by the user."""

    refs: list[dict[str, Any]] = []
    for message in reversed(runtime.state.get("messages", [])):
        role = (
            message.get("role") or message.get("type")
            if isinstance(message, dict)
            else getattr(message, "type", "")
        )
        if role not in {"user", "human"}:
            continue
        content = (
            message.get("content", [])
            if isinstance(message, dict)
            else getattr(message, "content", [])
        )
        if not isinstance(content, list):
            break
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text-plain":
                continue
            metadata = (
                block.get("metadata") if isinstance(block.get("metadata"), dict) else {}
            )
            title = str(
                metadata.get("filename") or block.get("title") or "Uploaded document"
            )
            text = block.get("text") if isinstance(block.get("text"), str) else ""
            if not text:
                continue
            refs.append(
                save_evidence(
                    runtime,
                    kind="upload",
                    locator=title,
                    title=title,
                    content=text,
                    segments=metadata.get("segments")
                    if isinstance(metadata.get("segments"), list)
                    else [],
                    truncated=bool(metadata.get("truncated")),
                )
            )
        break
    if not refs:
        return _tool_result(
            runtime,
            "No supported extracted uploads were present in the current request.",
            [],
        )
    lines = [
        f'[Evidence id="{ref["id"]}" kind="upload" locator="{ref["locator"]}"]'
        for ref in refs
    ]
    return _tool_result(runtime, "\n".join(lines), refs)


@tool
def read_workspace_source(file_path: str, runtime: ToolRuntime) -> Command:
    """Read and save one safe text file inside the selected workspace; never write or execute."""

    workspace = Path(_state_value(runtime, "workspace")).resolve()
    candidate = Path(file_path).expanduser()
    resolved = (
        (workspace / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    try:
        relative = resolved.relative_to(workspace).as_posix()
    except ValueError:
        return _tool_result(
            runtime,
            "Error: Access denied; the path is outside the selected workspace.",
            [],
        )
    if not resolved.is_file():
        return _tool_result(runtime, f"Error: File not found: {file_path}", [])
    if (
        resolved.name.lower() in SENSITIVE_NAMES
        or resolved.suffix.lower() in SENSITIVE_SUFFIXES
        or ".git" in resolved.parts
        or resolved.suffix.lower() in BINARY_EXTENSIONS
    ):
        return _tool_result(
            runtime, "Error: This sensitive or unsupported file cannot be read.", []
        )
    if resolved.stat().st_size > MAX_FILE_SIZE:
        return _tool_result(
            runtime, "Error: File exceeds the 100KB workspace evidence limit.", []
        )
    text = resolved.read_text(encoding="utf-8", errors="replace")
    ref = save_evidence(
        runtime, kind="workspace_file", locator=relative, title=relative, content=text
    )
    return _tool_result(
        runtime,
        f'[Evidence id="{ref["id"]}" kind="workspace_file" locator="{relative}"]\n{text}',
        [ref],
    )


@tool
def read_saved_source(source_id: str, runtime: ToolRuntime) -> str:
    """Reopen a source already saved for this session without another web request."""

    if runtime.store is None:
        return "Saved evidence is unavailable in this runtime."
    owner = _state_value(runtime, "user_identity", "anonymous") or "anonymous"
    thread = _state_value(runtime, "thread_identity")
    session_item = runtime.store.get((owner, "session-sources", thread), source_id)
    if session_item is None:
        return "Source is not referenced by this session."
    body = runtime.store.get((owner, "research-evidence"), source_id)
    if body is None:
        return "The saved source body is unavailable."
    value = body.value
    return (
        f'[Evidence id="{source_id}" kind="{value.get("kind", "source")}" '
        f'locator="{value.get("locator", "")}"]\n{value.get("content", "")}'
    )
