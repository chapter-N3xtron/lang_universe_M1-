"""Shared utilities for agent nodes in the LangGraph chat UI.

Every agent node receives the full accumulated State (including all prior
messages) from the Agent Server-managed PostgreSQL checkpointer. Use these helpers
so every agent — current and future — benefits from persistent thread state
without reimplementing history extraction.

Messages arrive as dicts with either LangGraph SDK format
(``{"type": "human", "content": "..."}``) or plain dict format
(``{"role": "user", "content": "..."}``).  Both are handled here.
"""

from typing import Any, TypedDict

from src.workspace_policy import ExecutionManifest


class AgentState(TypedDict, total=False):
    messages: list[dict]
    workspace: str
    mode: str
    model: str
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    execution_manifest: ExecutionManifest


def _msg_role(m: Any) -> str | None:
    """Normalise a message dict to ``"user"`` / ``"assistant"`` / ``"tool"`` / ``None``.

    LangGraph SDK serialises messages with ``"type": "human"`` while
    plain-dict messages use ``"role": "user"``.  Accept either.
    """
    if isinstance(m, dict):
        raw = m.get("role") or m.get("type")
    else:
        raw = getattr(m, "type", None)
    if raw in ("human", "user"):
        return "user"
    if raw in ("ai", "assistant"):
        return "assistant"
    if raw in ("tool",):
        return "tool"
    return None


def _msg_content(message: Any) -> Any:
    return (
        message.get("content", "")
        if isinstance(message, dict)
        else getattr(message, "content", "")
    )


def get_user_query(messages: list) -> str:
    """Return the most recent user message content."""
    for m in reversed(messages):
        if _msg_role(m) == "user":
            content = _msg_content(m)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_blocks: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        text_blocks.append(block)
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        text_blocks.append(block["text"])
                return "\n\n".join(text for text in text_blocks if text.strip())
    return ""


def get_conversation_history(messages: list) -> list[dict]:
    """Return all user and assistant turns as a clean list of {role, content} dicts."""
    result = []
    for m in messages:
        role = _msg_role(m)
        if role in ("user", "assistant"):
            result.append({"role": role, "content": _msg_content(m)})
    return result


def trim_history(messages: list, max_tokens: int = 4000) -> list:
    """Trim conversation history to fit within max_tokens while preserving tool-call/result pairs.

    Tool-call groups (an AIMessage with tool_calls followed by its ToolMessages)
    are treated as atomic units — they are never split during trimming.
    Keeps the most recent messages and drops from the start of the conversation.
    """
    if not messages:
        return messages

    # Group messages into atomic units
    groups = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        content = msg if isinstance(msg, dict) else {}
        is_tool_call = content.get("role") == "assistant" and bool(
            content.get("tool_calls", [])
        )

        if isinstance(msg, dict) and is_tool_call:
            group = [msg]
            i += 1
            # Collect following ToolMessages that belong to this tool call
            while i < len(messages):
                next_msg = messages[i]
                next_role = next_msg.get("role") if isinstance(next_msg, dict) else ""
                if next_role == "tool":
                    group.append(next_msg)
                    i += 1
                else:
                    break
            groups.append(group)
        else:
            groups.append([msg])
            i += 1

    # Estimate tokens per message
    def estimate(msg: dict) -> int:
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content) // 4 + 10
        return 20

    def group_tokens(group: list) -> int:
        return sum(estimate(m) for m in group)

    total = sum(group_tokens(g) for g in groups)
    if total <= max_tokens:
        return messages

    # Drop groups from the start until we fit
    kept = groups[:]
    while len(kept) > 1 and sum(group_tokens(g) for g in kept) > max_tokens:
        kept.pop(0)

    return [m for g in kept for m in g]
