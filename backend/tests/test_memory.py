"""Tests for durable conversation memory via LangGraph checkpointer."""

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

        app.invoke(
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
        )

        result = app.invoke(
            {
                "messages": [{"role": "user", "content": "turn two"}],
                "workspace": "/tmp",
                "target_agent": "jasper",
                "mode": "live",
                "model": None,
            },
            config=config,
        )

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
            app.invoke(
                {
                    "messages": [{"role": "user", "content": phrase}],
                    "workspace": "/tmp",
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
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
        opencode_agent = importlib.import_module("src.opencode_agent")

        captured = {}

        def fake_run_opencode(*, session_id=None, **kwargs):
            captured["session_id_in"] = session_id
            return {
                "success": True,
                "session_id": "sess-123",
                "text": "ok",
                "artifacts": [],
                "events": [],
                "error": None,
            }

        monkeypatch.setattr(opencode_agent, "run_opencode", fake_run_opencode)

        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-opencode-session"}}

        result1 = app.invoke(
            {
                "messages": [{"role": "user", "content": "first"}],
                "workspace": "/tmp",
                "target_agent": "opencode",
                "mode": "live",
                "model": None,
            },
            config=config,
        )
        assert captured["session_id_in"] is None
        assert result1["opencode_session_id"] == "sess-123"

        captured.clear()
        app.invoke(
            {
                "messages": [{"role": "user", "content": "second"}],
                "workspace": "/tmp",
                "target_agent": "opencode",
                "mode": "live",
                "model": None,
            },
            config=config,
        )
        assert captured["session_id_in"] == "sess-123"
