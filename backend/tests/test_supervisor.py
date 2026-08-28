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
    for key in (
        "src.chat_ui",
        "src.jasper_agent",
        "src.research_agent",
        "src.librarian_agent",
        "src.magic_coder_graph",
        "src.llm",
    ):
        sys.modules.pop(key, None)


def test_compiled_graph_uses_jasper_as_the_only_coding_boundary():
    _clear_src_modules()
    from src.chat_ui import create_chat_ui

    graph = _compile(create_chat_ui()).get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert "coding" not in graph.nodes
    assert ("prepare_jasper", "jasper") in edges
    assert ("jasper", "route_jasper_result") in edges
    assert ("route_jasper_result", "record_session") in edges
    assert ("record_session", "__end__") in edges


def test_compiled_graph_routes_local_jasper_librarian_exit():
    _clear_src_modules()
    from src.chat_ui import create_chat_ui

    graph = _compile(create_chat_ui()).get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert ("route_jasper_result", "librarian") in edges
    assert ("librarian", "prepare_jasper") in edges
    assert ("jasper", "librarian") not in edges
    assert ("jasper", "research") not in edges
    assert ("supervisor", "research") not in edges
    assert "research" not in graph.nodes


def test_compiled_graph_declares_visible_librarian_route():
    _clear_src_modules()
    from src.chat_ui import create_chat_ui, supervisor_node

    graph = _compile(create_chat_ui()).get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}

    assert ("supervisor", "librarian") in edges
    assert ("librarian", "record_session") in edges

    command = supervisor_node(
        {
            "messages": [{"role": "user", "content": "Ask The Librarian."}],
            "target_agent": "librarian",
        }
    )
    assert command.goto == "librarian"
    assert command.update["active_agent"] == "librarian"


def test_new_session_opening_is_canonical_and_model_free():
    from src import chat_ui
    from src.jasper_agent import STANDARD_SESSION_GREETING

    with patch.object(chat_ui, "get_llm") as get_llm:
        command = chat_ui.supervisor_node(
            {"messages": [], "session_event": "open", "session_opened": False}
        )
    assert command.goto == "session_opening"
    get_llm.assert_not_called()

    opening = chat_ui.session_opening_node({})
    assert opening["messages"] == [
        {"role": "assistant", "content": STANDARD_SESSION_GREETING}
    ]
    assert opening["session_opened"] is True
    assert opening["active_agent"] == "jasper"

    duplicate = chat_ui.session_opening_node(
        {"messages": [{"role": "assistant", "content": STANDARD_SESSION_GREETING}]}
    )
    assert duplicate["messages"] == []
    assert duplicate["session_opened"] is True


def test_legacy_research_selection_routes_to_librarian():
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("Here is the research result."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-route-research"}}

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research the latest AI news"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "research",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    # The legacy identifier remains accepted but is normalized before routing.
    assert len(result["handoff_history"]) >= 1
    assert result["handoff_history"][0]["to"] == "librarian"
    assert len(result["decision_log"]) >= 1
    assert "librarian" in result["decision_log"][0]["decision"]
    # Specialist should have produced an assistant message
    msgs = result.get("messages", [])
    assert len(msgs) >= 2, "Expected user + assistant messages"
    assert msgs[-1]["role"] == "assistant"


def test_supervisor_audit_trail():
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("Here is the research result."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-audit-trail"}}

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": "Research AI, then write code"}
                    ],
                    "workspace": "/tmp",
                    "target_agent": "research",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    assert len(result["handoff_history"]) >= 1
    assert result["handoff_history"][0]["to"] == "librarian"
    assert len(result["decision_log"]) >= 1
    assert "librarian" in result["decision_log"][0]["decision"]


def test_state_accumulation_across_turns():
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("Response to turn one."),
            _make_llm_response("done"),
            _make_llm_response("Response to turn two."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-accumulation"}}

        asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "turn one"}],
                    "workspace": "/tmp",
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "turn two"}],
                    "workspace": "/tmp",
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    contents = [m["content"] for m in result["messages"]]
    assert "turn one" in contents
    assert "turn two" in contents
    assert result["messages"][-1]["role"] == "assistant"


def test_thread_isolation():
    mock_llm = _create_mock_llm(
        [
            _make_llm_response("jasper"),
            _make_llm_response("jasper"),
            _make_llm_response("Response A."),
            _make_llm_response("done"),
            _make_llm_response("jasper"),
            _make_llm_response("jasper"),
            _make_llm_response("Response B."),
            _make_llm_response("done"),
        ]
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())

        def run_turns(thread_id: str, phrase: str):
            config = {"configurable": {"thread_id": thread_id}}
            asyncio.run(
                app.ainvoke(
                    {
                        "messages": [{"role": "user", "content": phrase}],
                        "workspace": "/tmp",
                        "target_agent": "",
                        "mode": "live",
                        "model": None,
                    },
                    config=config,
                )
            )
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

        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "workspace": "/tmp",
                    "target_agent": "",
                    "mode": "live",
                    "model": None,
                },
                config=config,
            )
        )

    # "done" now falls back to jasper → routes through approval → pending_approval=True
    assert result.get("pending_agent", "") == "jasper"
    assert result.get("pending_approval", False) is True


def test_jasper_visual_response_survives_outer_graph_state(tmp_path):
    """Structured artifacts use persisted LangGraph state, not a side channel."""

    async def fake_call_jasper(state):
        return {
            "messages": [AIMessage(id="jasper-visual-1", content="Here is the flow.")],
            "jasper_structured_response": {
                "version": 1,
                "voice_text": "Here is the flow.",
                "artifacts": [
                    {
                        "renderer": "react_flow",
                        "artifact_id": "flow-1",
                        "title": "Request flow",
                        "alt_text": "Input flows to output.",
                        "source_message_id": "jasper-visual-1",
                        "payload": {
                            "nodes": [
                                {"id": "input", "label": "Input", "kind": "input"},
                                {
                                    "id": "output",
                                    "label": "Output",
                                    "kind": "output",
                                },
                            ],
                            "edges": [
                                {
                                    "source": "input",
                                    "target": "output",
                                    "relation": "flows_to",
                                }
                            ],
                            "direction": "left_to_right",
                        },
                    }
                ],
                "layout_suggestion": {
                    "mode": "split",
                    "reason": "See the flow beside the explanation.",
                },
                "diagnostic": None,
            },
            "visual_artifacts": [
                {
                    "renderer": "react_flow",
                    "artifact_id": "flow-1",
                    "title": "Request flow",
                    "alt_text": "Input flows to output.",
                    "source_message_id": "jasper-visual-1",
                    "payload": {
                        "nodes": [{"id": "input", "label": "Input"}],
                        "edges": [],
                        "direction": "left_to_right",
                    },
                }
            ],
            "layout_suggestion": {
                "mode": "split",
                "reason": "See the flow beside the explanation.",
            },
            "jasper_strategy": "two_pass",
            "jasper_diagnostic": None,
        }

    _clear_src_modules()
    with patch("src.jasper_agent.call_jasper", side_effect=fake_call_jasper):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "test-visual-state"}}
        result = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "Draw the flow"}],
                    "workspace": str(tmp_path),
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": "ollama/test-model",
                },
                config=config,
            )
        )

    assert result["jasper_structured_response"]["voice_text"] == "Here is the flow."
    assert result["visual_artifacts"][0]["artifact_id"] == "flow-1"
    assert result["layout_suggestion"]["mode"] == "split"
    assert result["jasper_strategy"] == "two_pass"

    persisted = app.get_state(config).values
    assert persisted["visual_artifacts"] == result["visual_artifacts"]
    assert (
        persisted["jasper_structured_response"] == result["jasper_structured_response"]
    )


def test_explicit_jasper_selection_stays_sticky_across_turns(tmp_path):
    async def fake_call_jasper(state):
        user_text = state["messages"][-1].content
        return {
            "messages": [AIMessage(content=f"Jasper handled: {user_text}")],
            "visual_artifacts": [],
        }

    _clear_src_modules()
    with patch("src.jasper_agent.call_jasper", side_effect=fake_call_jasper):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        config = {"configurable": {"thread_id": "sticky-jasper"}}
        first = asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "First request"}],
                    "workspace": str(tmp_path),
                    "target_agent": "jasper",
                    "mode": "live",
                    "model": "ollama/test-model",
                },
                config=config,
            )
        )
        second = asyncio.run(
            app.ainvoke(
                {"messages": [{"role": "user", "content": "Draw a concept map"}]},
                config=config,
            )
        )

    assert first["target_agent"] == "jasper"
    assert second["target_agent"] == "jasper"
    assert second["messages"][-1]["content"].startswith("Jasper handled:")
    decisions = [entry["decision"] for entry in second["decision_log"]]
    assert decisions.count("route_to_jasper") == 2
    assert "route_to_magic-coder" not in decisions


def test_jasper_passes_selected_workspace_and_langgraph_thread_to_coding(tmp_path):
    captured = []

    async def fake_call_jasper(state):
        captured.append(state)
        return {
            "messages": [AIMessage(content="Jasper handled the request.")],
            "visual_artifacts": [],
        }

    _clear_src_modules()
    with patch("src.jasper_agent.call_jasper", side_effect=fake_call_jasper):
        from src.chat_ui import create_chat_ui

        app = _compile(create_chat_ui())
        asyncio.run(
            app.ainvoke(
                {
                    "messages": [{"role": "user", "content": "Use Coding"}],
                    "workspace": str(tmp_path),
                    "target_agent": "jasper",
                    "mode": "read_only",
                    "model": "ollama/test-model",
                },
                config={"configurable": {"thread_id": "jasper-coding-thread"}},
            )
        )

    assert captured[0]["workspace"] == str(tmp_path.resolve())
    assert captured[0]["execution_manifest"]["selected_repository"] == str(
        tmp_path.resolve()
    )
    assert captured[0]["thread_identity"] == "jasper-coding-thread"


def test_legacy_coding_selection_enters_the_jasper_boundary(tmp_path):
    jasper_inputs = []

    async def fake_call_jasper(state):
        jasper_inputs.append(state)
        return {
            "messages": [AIMessage(content="Jasper accepted the coding request.")],
            "visual_artifacts": [],
        }

    _clear_src_modules()
    with patch("src.jasper_agent.call_jasper", side_effect=fake_call_jasper):
        from src.chat_ui import create_chat_ui

        builder = create_chat_ui()
        result = asyncio.run(
            _compile(builder).ainvoke(
                {
                    "messages": [{"role": "user", "content": "Use Coder"}],
                    "workspace": str(tmp_path),
                    "target_agent": "coding",
                    "execution_mode": "read_only",
                    "model": "ollama/test-model",
                    "user_identity": "test-user",
                },
                config={"configurable": {"thread_id": "coding-alias-thread"}},
            )
        )

    assert "coding" not in builder.nodes
    assert jasper_inputs[0]["execution_mode"] == "read_only"
    assert jasper_inputs[0]["thread_identity"] == "coding-alias-thread"
    assert jasper_inputs[0]["user_identity"] == "test-user"
    assert result["messages"][-1]["content"] == "Jasper accepted the coding request."


def test_auto_concept_map_routing_is_owned_by_jasper_without_model_guessing():
    _clear_src_modules()
    from src import chat_ui

    with patch.object(chat_ui, "get_llm", side_effect=AssertionError("not needed")):
        result = chat_ui.supervisor_node(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Draw a concept map of the request flow",
                    }
                ],
                "target_agent": "",
            }
        )

    assert result.update["pending_agent"] == "jasper"
    assert result.update["decision_log"][0]["reason"] == (
        "Deterministic visual-artifact ownership"
    )
