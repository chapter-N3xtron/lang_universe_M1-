"""Shared utilities for agent nodes in the LangGraph chat UI.

Every agent node receives the full accumulated State (including all prior
messages) from the outer graph's SQLite checkpointer.  Use these helpers
so every agent — current and future — benefits from persistent memory
without reimplementing history extraction.
"""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict]
    workspace: str
    mode: str
    model: str
    opencode_session_id: str


def get_user_query(messages: list[dict]) -> str:
    """Return the most recent user message content."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "")
    return ""


def get_conversation_history(messages: list[dict]) -> list[dict]:
    """Return all user and assistant turns as a clean list of {role, content} dicts."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
    ]
