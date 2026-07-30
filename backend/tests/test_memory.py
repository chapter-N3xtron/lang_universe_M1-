"""Tests for durable conversation memory via LangGraph checkpointer."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver


def _compile(app):
    return app.compile(checkpointer=InMemorySaver())


def _make_llm_response(content: str):
    return AIMessage(content=content)


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_thread_memory_accumulates_messages():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("done")
    mock_llm.bind_tools.return_value = mock_llm

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
    mock_llm.bind_tools.return_value = mock_llm

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
