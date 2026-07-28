"""Tests for durable conversation memory via LangGraph checkpointer."""

import asyncio
import importlib
import sys
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import InMemorySaver


def _compile(app):
    return app.compile(checkpointer=InMemorySaver())


def _make_llm_response(content: str):
    mock = MagicMock()
    mock.content = content
    return mock


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_thread_memory_accumulates_messages():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("done")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        thread_id = "test-memory-thread"
        config = {"configurable": {"thread_id": thread_id}}

        asyncio.run(app.ainvoke(
            {
                "messages": [
                    {"role": "assistant", "content": "welcome"},
                    {"role": "user", "content": "turn one"},
                ],
                "workspace": "/tmp",
                "target_agent": "jasper",
                "mode": "live",
                "model": None,
            },
            config=config,
        ))

        result = asyncio.run(app.ainvoke(
            {
                "messages": [{"role": "user", "content": "turn two"}],
                "workspace": "/tmp",
                "target_agent": "jasper",
                "mode": "live",
                "model": None,
            },
            config=config,
        ))

    contents = [m["content"] for m in result["messages"]]
    assert "turn one" in contents
    assert "turn two" in contents
    assert result["messages"][-1]["role"] == "assistant"

    snapshot = app.get_state(config)
    assert snapshot is not None
    snapshot_contents = [m["content"] for m in snapshot.values["messages"]]
    assert "turn one" in snapshot_contents
    assert "turn two" in snapshot_contents


def test_thread_isolation():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("done")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())

        def run_turns(thread_id: str, phrase: str):
            config = {"configurable": {"thread_id": thread_id}}
            asyncio.run(app.ainvoke(
                {
                    "messages": [{"role": "user", "content": phrase}],
                    "workspace": "/tmp",
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            ))
            snapshot = app.get_state(config)
            return [m["content"] for m in snapshot.values["messages"]]

        a = run_turns("thread-a", "phrase-a")
        b = run_turns("thread-b", "phrase-b")

    assert "phrase-a" in a
    assert "phrase-b" not in a
    assert "phrase-b" in b
    assert "phrase-a" not in b


def test_opencode_session_id_persists_in_state(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("done")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        opencode_cli = importlib.import_module("src.opencode_cli")

        captured = {}

        async def fake_run_opencode_stream(
            message="", title="", workspace="", model="",
            auto_approve=False, history=None, session_id=None,
        ):
            captured["session_id_in"] = session_id
            yield {"type": "complete", "session_id": "sess-123", "text": "ok", "artifacts": []}

        monkeypatch.setattr(
            opencode_cli, "run_opencode_stream", fake_run_opencode_stream
        )

        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-opencode-session"}}

        async def run_turn(messages, config):
            return await app.ainvoke(
                {
                    "messages": messages,
                    "workspace": "/tmp",
                    "target_agent": "opencode",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )

        result1 = asyncio.run(run_turn(
            [{"role": "user", "content": "first"}], config
        ))
        assert captured["session_id_in"] is None
        assert result1["opencode_session_id"] == "sess-123"

        captured.clear()
        result2 = asyncio.run(run_turn(
            [{"role": "user", "content": "second"}], config
        ))
        assert captured["session_id_in"] == "sess-123"
