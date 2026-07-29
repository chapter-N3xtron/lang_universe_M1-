"""Tests for the manual supervisor graph in chat_ui.py.

These tests verify the supervisor graph's routing, audit trail, state
accumulation, thread isolation, and end-turn behavior.  All LLM calls
are mocked so the tests are fast and deterministic.

Per LangGraph docs (https://docs.langchain.com/oss/python/langgraph/graph-api#command):
"Command only adds dynamic edges—static edges defined with add_edge still
execute. For each node, use either Command or static edges to route to the
next nodes, not both."

The supervisor node uses Command for routing.  Specialist nodes use static
edges back to supervisor.  This is the documented pattern.
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver


def _compile(app):
    return app.compile(checkpointer=InMemorySaver())


def _make_llm_response(content: str):
    return AIMessage(content=content)


def _create_mock_llm(responses):
    call_count = [0]

    def mock_invoke(messages):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    mock = MagicMock()
    mock.invoke.side_effect = mock_invoke
    mock.bind_tools.return_value = mock
    return mock


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_supervisor_routes_to_research():
    mock_llm = _create_mock_llm([
        _make_llm_response("Here is the research result."),
        _make_llm_response("done"),
    ])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-route-research"}}

        result = asyncio.run(app.ainvoke(
            {
                "messages": [{"role": "user", "content": "Research the latest AI news"}],
                "workspace": "/tmp",
                "target_agent": "research",
                "mode": "live",
                "model": None,
            },
            config=config,
        ))

    # target_agent=research routes directly (bypasses approval), produces a response,
    # then supervisor re-runs and ends the turn (active_agent cleared).
    assert len(result["handoff_history"]) >= 1
    assert result["handoff_history"][0]["to"] == "research"
    assert len(result["decision_log"]) >= 1
    assert "research" in result["decision_log"][0]["decision"]
    # Specialist should have produced an assistant message
    msgs = result.get("messages", [])
    assert len(msgs) >= 2, "Expected user + assistant messages"
    assert msgs[-1]["role"] == "assistant"


def test_supervisor_audit_trail():
    mock_llm = _create_mock_llm([
        _make_llm_response("Here is the research result."),
        _make_llm_response("done"),
    ])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-audit-trail"}}

        result = asyncio.run(app.ainvoke(
            {
                "messages": [{"role": "user", "content": "Research AI, then write code"}],
                "workspace": "/tmp",
                "target_agent": "research",
                "mode": "live",
                "model": None,
            },
            config=config,
        ))

    assert len(result["handoff_history"]) >= 1
    assert result["handoff_history"][0]["to"] == "research"
    assert len(result["decision_log"]) >= 1
    assert "research" in result["decision_log"][0]["decision"]


def test_state_accumulation_across_turns():
    mock_llm = _create_mock_llm([
        _make_llm_response("Response to turn one."),
        _make_llm_response("done"),
        _make_llm_response("Response to turn two."),
        _make_llm_response("done"),
    ])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-accumulation"}}

        asyncio.run(app.ainvoke(
            {
                "messages": [{"role": "user", "content": "turn one"}],
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


def test_thread_isolation():
    mock_llm = _create_mock_llm([
        _make_llm_response("jasper"),
        _make_llm_response("jasper"),
        _make_llm_response("Response A."),
        _make_llm_response("done"),
        _make_llm_response("jasper"),
        _make_llm_response("jasper"),
        _make_llm_response("Response B."),
        _make_llm_response("done"),
    ])

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
                    "target_agent": "",
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


def test_supervisor_done_falls_back_to_jasper():
    """When the supervisor LLM returns 'done', the graph should fall back to
    routing to jasper (via approval) instead of ending silently with no response."""
    mock_llm = _create_mock_llm([_make_llm_response("done")])

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui
        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-end-turn"}}

        result = asyncio.run(app.ainvoke(
            {
                "messages": [{"role": "user", "content": "Hello"}],
                "workspace": "/tmp",
                "target_agent": "",
                "mode": "live",
                "model": None,
            },
            config=config,
        ))

    # "done" now falls back to jasper → routes through approval → pending_approval=True
    assert result.get("pending_agent", "") == "jasper"
    assert result.get("pending_approval", False) is True
