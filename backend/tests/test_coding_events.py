"""Tests for the bounded coding-agent frontend event contract."""

import json

from langchain_core.messages import AIMessage, AIMessageChunk

from src.coding_events import (
    MAX_EVENTS_PER_RUN,
    MAX_TRANSIENT_TEXT_CHARS,
    TEXT_BATCH_CHARS,
    CodingEventEmitter,
)


def test_text_is_batched_and_bounded():
    written = []
    emitter = CodingEventEmitter(written.append, "session")

    emitter.text("a" * (TEXT_BATCH_CHARS - 1))
    assert written == []
    emitter.text("b")
    assert written[0]["data"]["content"] == "a" * (TEXT_BATCH_CHARS - 1) + "b"

    emitter.text("x" * (MAX_TRANSIENT_TEXT_CHARS * 2))
    emitter.flush_text()
    emitted = sum(
        len(event["data"]["content"]) for event in written if event["kind"] == "text"
    )
    assert emitted == MAX_TRANSIENT_TEXT_CHARS


def test_event_count_is_bounded_and_versioned():
    written = []
    emitter = CodingEventEmitter(written.append, "opaque-session")
    for index in range(MAX_EVENTS_PER_RUN * 2):
        emitter.emit("status", "running", index=index)

    assert len(written) == MAX_EVENTS_PER_RUN
    assert [event["sequence"] for event in written] == list(range(MAX_EVENTS_PER_RUN))
    assert all(event["version"] == 1 for event in written)
    assert all(event["session_id"] == "opaque-session" for event in written)


def test_native_events_are_summarized_without_tool_payloads():
    written = []
    emitter = CodingEventEmitter(written.append, "session")
    emitter.consume(("messages", (AIMessageChunk(content="hello"), {})))
    emitter.consume(
        (
            "updates",
            {
                "agent": {
                    "messages": AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "approved_write_file",
                                "id": "call-1",
                                "args": {"secret": "must-not-leak"},
                            }
                        ],
                    )
                }
            },
        )
    )
    emitter.flush_text()

    serialized = json.dumps(written)
    assert "must-not-leak" not in serialized
    assert any(event["kind"] == "file" for event in written)
    assert any(event["kind"] == "text" for event in written)
