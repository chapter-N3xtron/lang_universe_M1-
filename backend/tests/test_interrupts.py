"""Tests for human-in-the-loop interrupts in the supervisor graph."""

import sys
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def _compile(app):
    return app.compile(checkpointer=InMemorySaver())


def _make_llm_response(content: str):
    mock = MagicMock()
    mock.content = content
    return mock


def _create_mock_llm(responses):
    call_count = [0]

    def mock_invoke(messages):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    mock = MagicMock()
    mock.invoke.side_effect = mock_invoke
    return mock


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_interrupt_fires_on_handoff():
    mock_llm = _create_mock_llm([_make_llm_response("research")])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-fires"}}

        result = app.invoke(
            {
                "messages": [{"role": "user", "content": "Research the latest AI news"}],
                "workspace": "/tmp",
                "target_agent": "",
                "mode": "live",
                "model": None,
            },
            config=config,
        )

    state = app.get_state(config)
    assert state is not None
    assert len(state.tasks) > 0
    interrupts = state.tasks[0].interrupts
    assert len(interrupts) > 0
    interrupt_data = interrupts[0].value
    assert interrupt_data["agent"] == "research"
    assert "question" in interrupt_data


def test_interrupt_approval_proceeds():
    mock_llm = _create_mock_llm([
        _make_llm_response("research"),
        _make_llm_response("research"),
        _make_llm_response("Here is the research result."),
        _make_llm_response("done"),
    ])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-approve"}}

        app.invoke(
            {
                "messages": [{"role": "user", "content": "Research the latest AI news"}],
                "workspace": "/tmp",
                "target_agent": "",
                "mode": "live",
                "model": None,
            },
            config=config,
        )

        result = app.invoke(Command(resume=True), config=config)

    assert len(result.get("handoff_history", [])) >= 1
    assert result["handoff_history"][0]["to"] == "research"
    msgs = result.get("messages", [])
    assert len(msgs) >= 1


def test_interrupt_rejection_stops():
    mock_llm = _create_mock_llm([_make_llm_response("research")])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-reject"}}

        app.invoke(
            {
                "messages": [{"role": "user", "content": "Research the latest AI news"}],
                "workspace": "/tmp",
                "target_agent": "",
                "mode": "live",
                "model": None,
            },
            config=config,
        )

        result = app.invoke(Command(resume=False), config=config)

    assert result.get("active_agent", "") == ""
    assert result.get("pending_approval", False) is False
    assert len(result.get("handoff_history", [])) == 0
