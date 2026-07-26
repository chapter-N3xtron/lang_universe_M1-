"""Shared utilities for agent nodes in the LangGraph chat UI.

Every agent node receives the full accumulated State (including all prior
messages) from the outer graph's SQLite checkpointer.  Use these helpers
so every agent — current and future — benefits from persistent memory
without reimplementing history extraction.

Messages arrive as dicts with either LangGraph SDK format
(``{"type": "human", "content": "..."}``) or plain dict format
(``{"role": "user", "content": "..."}``).  Both are handled here.
"""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict]
    workspace: str
    mode: str
    model: str
    opencode_session_id: str


def _msg_role(m: dict) -> str | None:
    """Normalise a message dict to ``"user"`` / ``"assistant"`` / ``"tool"`` / ``None``.

    LangGraph SDK serialises messages with ``"type": "human"`` while
    plain-dict messages use ``"role": "user"``.  Accept either.
    """
    raw = m.get("role") or m.get("type")
    if raw in ("human", "user"):
        return "user"
    if raw in ("ai", "assistant"):
        return "assistant"
    if raw in ("tool",):
        return "tool"
    return None


def get_user_query(messages: list[dict]) -> str:
    """Return the most recent user message content."""
    for m in reversed(messages):
        if isinstance(m, dict) and _msg_role(m) == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                return content[0].get("text", "")
    return ""


def get_conversation_history(messages: list[dict]) -> list[dict]:
    """Return all user and assistant turns as a clean list of {role, content} dicts."""
    result = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = _msg_role(m)
        if role in ("user", "assistant"):
            result.append({"role": role, "content": m.get("content", "")})
    return result
