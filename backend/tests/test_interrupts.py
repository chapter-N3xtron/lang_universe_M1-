"""Tests for human-in-the-loop interrupts in the supervisor graph."""

import asyncio
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

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    state = app.get_state(config)
    assert state is not None
    assert len(state.tasks) > 0
    interrupts = state.tasks[0].interrupts
    assert len(interrupts) > 0
    interrupt_data = interrupts[0].value
    # New HITL schema: {action_requests: [{name, args}], review_configs: [...]}
    assert "action_requests" in interrupt_data
    assert len(interrupt_data["action_requests"]) == 1
    assert interrupt_data["action_requests"][0]["args"]["agent"] == "librarian"
    assert "review_configs" in interrupt_data
    assert "approve" in interrupt_data["review_configs"][0]["allowed_decisions"]


def test_interrupt_approval_proceeds():
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("research"),
            _make_llm_response("research"),
            _make_llm_response("Here is the research result."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-approve"}}

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

        result = asyncio.run(app.ainvoke(Command(resume=True), config=config))

    assert len(result.get("handoff_history", [])) >= 1
    assert result["handoff_history"][0]["to"] == "librarian"
    msgs = result.get("messages", [])
    assert len(msgs) >= 1


def test_interrupt_approval_proceeds_via_decision_dict():
    """Verify the approval node accepts the new HITL Decision dict format
    that the Agent Chat UI sends via {decisions: [{type: "approve"}]}."""
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("research"),
            _make_llm_response("research"),
            _make_llm_response("Here is the research result."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-approve-dict"}}

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

        result = asyncio.run(
            app.ainvoke(
                Command(resume=[{"type": "approve"}]),
                config=config,
            )
        )

    assert len(result.get("handoff_history", [])) >= 1
    assert result["handoff_history"][0]["to"] == "librarian"
    msgs = result.get("messages", [])
    assert len(msgs) >= 1


def test_interrupt_rejection_stops():
    mock_llm = _create_mock_llm([_make_llm_response("research")])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-reject"}}

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

        result = asyncio.run(app.ainvoke(Command(resume=False), config=config))

    assert result.get("active_agent", "") == ""
    assert result.get("pending_approval", False) is False
    assert len(result.get("handoff_history", [])) == 0


def test_interrupt_rejection_stops_via_decision_dict():
    """Verify the approval node accepts a reject Decision dict from the UI."""
    mock_llm = _create_mock_llm([_make_llm_response("research")])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-interrupt-reject-dict"}}

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

        result = asyncio.run(
            app.ainvoke(
                Command(resume=[{"type": "reject", "message": "no thanks"}]),
                config=config,
            )
        )

    assert result.get("active_agent", "") == ""
    assert result.get("pending_approval", False) is False
    assert len(result.get("handoff_history", [])) == 0


def test_supervisor_fallback_to_jasper_on_done():
    """When the supervisor LLM returns 'done' on the first message, the graph
    should fall back to jasper instead of ending with no response."""
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("done"),
            _make_llm_response("Hi, I'm Jasper. How can I help?"),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-fallback-jasper"}}

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "hello"}],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    # Should route through approval → jasper, producing an assistant message
    msgs = result.get("messages", [])
    assert len(msgs) >= 1, (
        "Expected at least one assistant message from jasper fallback"
    )


def test_supervisor_fallback_on_unrecognized_agent():
    """When the supervisor LLM returns an unrecognized agent name, fall back to jasper."""
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("banana"),
            _make_llm_response("Hi, I'm Jasper."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-fallback-unrecognized"}}

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "hello"}],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    # Should fall back to jasper, producing a message
    msgs = result.get("messages", [])
    assert len(msgs) >= 1, "Expected jasper fallback message for unrecognized agent"
