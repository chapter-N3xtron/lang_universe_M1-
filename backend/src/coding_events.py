"""Bounded, versioned frontend event contract for coding-agent runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CODING_EVENT_VERSION = 1
MAX_EVENTS_PER_RUN = 128
TEXT_BATCH_CHARS = 512
MAX_TRANSIENT_TEXT_CHARS = 16_384


class CodingEventEmitter:
    """Translate native LangGraph events into bounded custom-event envelopes."""

    def __init__(self, writer: Callable[[dict[str, Any]], None], session_id: str):
        self.writer = writer
        self.session_id = session_id
        self.events: list[dict[str, Any]] = []
        self.sequence = 0
        self._text_buffer = ""
        self._text_emitted = 0
        self._tool_ids: set[str] = set()
        self.latest_values: dict[str, Any] = {}

    def emit(self, kind: str, status: str, **data: Any) -> None:
        if len(self.events) >= MAX_EVENTS_PER_RUN:
            return
        event = {
            "type": "coding_event",
            "version": CODING_EVENT_VERSION,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "kind": kind,
            "status": status,
            "data": data,
        }
        self.sequence += 1
        self.events.append(event)
        self.writer(event)

    def text(self, content: str) -> None:
        buffered = self._text_emitted + len(self._text_buffer)
        if not content or buffered >= MAX_TRANSIENT_TEXT_CHARS:
            return
        remaining = MAX_TRANSIENT_TEXT_CHARS - buffered
        self._text_buffer += content[:remaining]
        if len(self._text_buffer) >= TEXT_BATCH_CHARS:
            self.flush_text()

    def flush_text(self) -> None:
        if not self._text_buffer:
            return
        content = self._text_buffer
        self._text_buffer = ""
        self._text_emitted += len(content)
        self.emit("text", "streaming", content=content, transient=True)

    def tool(self, name: str, tool_call_id: str = "", status: str = "running") -> None:
        identity = tool_call_id or f"{name}:{status}:{len(self._tool_ids)}"
        dedupe_key = f"{identity}:{status}"
        if dedupe_key in self._tool_ids:
            return
        self._tool_ids.add(dedupe_key)
        category = "tool"
        if name in {"task", "launch_task", "general-purpose"}:
            category = "subagent"
        elif "plan" in name or "todo" in name:
            category = "plan"
        elif name in {
            "approved_write_file",
            "approved_edit_file",
            "write_file",
            "edit_file",
            "delete",
        }:
            category = "file"
        self.emit(category, status, name=name, tool_call_id=tool_call_id)

    def consume(self, event: Any) -> None:
        """Consume native ``astream`` messages/updates without exposing args/output."""
        mode, payload = _stream_payload(event)
        if mode == "messages":
            message = payload[0] if isinstance(payload, tuple) and payload else payload
            self._consume_message(message)
        elif mode == "updates":
            self._consume_update(payload)
        elif mode == "values" and isinstance(payload, dict):
            self.latest_values = payload

    def _consume_message(self, message: Any) -> None:
        content = getattr(message, "content", "")
        if isinstance(content, str) and getattr(message, "type", "") in {
            "AIMessageChunk",
            "ai",
        }:
            self.text(content)
        for call in getattr(message, "tool_calls", []) or []:
            self.tool(str(call.get("name", "unknown")), str(call.get("id", "")))
        for chunk in getattr(message, "tool_call_chunks", []) or []:
            name = chunk.get("name")
            if name:
                self.tool(str(name), str(chunk.get("id", "")))

    def _consume_update(self, update: Any) -> None:
        if isinstance(update, dict):
            for key, value in update.items():
                if key in {"messages", "message"}:
                    values = value if isinstance(value, list) else [value]
                    for message in values:
                        self._consume_message(message)
                elif isinstance(value, (dict, list, tuple)):
                    self._consume_update(value)
        elif isinstance(update, (list, tuple)):
            for value in update:
                self._consume_update(value)


def _stream_payload(event: Any) -> tuple[str, Any]:
    if isinstance(event, tuple):
        if len(event) == 3 and isinstance(event[1], str):
            return event[1], event[2]
        if len(event) == 2 and isinstance(event[0], str):
            return event[0], event[1]
    return "updates", event
