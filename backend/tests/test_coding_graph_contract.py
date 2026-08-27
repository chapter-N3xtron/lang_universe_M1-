"""Contract tests for the authoritative complete Coder graph."""

import ast
import asyncio
import operator
from pathlib import Path
from types import SimpleNamespace
from typing import get_args, get_type_hints

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph.ui import ui_message_reducer

_INPUT_FIELDS = {
    "messages",
    "workspace",
    "model",
    "execution_mode",
    "thread_identity",
    "user_identity",
    "coding_session_id",
}
_OUTPUT_FIELDS = {
    "messages",
    "workspace",
    "execution_manifest",
    "coding_session_id",
    "coding_status",
    "ui",
}
_MUTABLE_TOOL_NAMES = [
    "custodian_compose_prepare_environment",
    "custodian_compose_read",
    "custodian_compose_change",
    "custodian_github_publish",
]


class _ResultApp:
    def __init__(self, *, todos=None, error=None):
        self.todos = todos or []
        self.error = error

    async def ainvoke(self, payload, config=None):
        del config
        if self.error is not None:
            raise self.error
        return {
            "messages": [*payload["messages"], AIMessage(content="Coder result")],
            "todos": self.todos,
        }


def _invoke_graph(monkeypatch, tmp_path, *, todos=None, error=None):
    from src import coding_agent

    async def session_agent(*_args):
        return _ResultApp(todos=todos, error=error)

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)
    return asyncio.run(
        coding_agent.create_coding_agent_graph().ainvoke(
            {
                "messages": [{"role": "user", "content": "Do the work"}],
                "workspace": str(tmp_path),
                "model": "test-model",
                "execution_mode": "read_only",
                "thread_identity": "contract-thread",
                "user_identity": "contract-user",
                "coding_session_id": "existing-session",
                "ui": [],
            }
        )
    )


def test_authoritative_graph_declares_shared_schemas_topology_and_no_persistence():
    from src import coding_agent

    graph = coding_agent.create_coding_agent_graph()

    assert graph.builder.state_schema is coding_agent.CoderState
    assert graph.builder.input_schema is coding_agent.CoderInputState
    assert graph.builder.output_schema is coding_agent.CoderOutputState
    assert coding_agent.CodingAgentState is coding_agent.CoderState
    assert set(graph.get_input_jsonschema()["properties"]) == _INPUT_FIELDS
    assert set(graph.get_output_jsonschema()["properties"]) == _OUTPUT_FIELDS
    assert set(graph.get_graph().nodes) == {"__start__", "coding_agent", "__end__"}
    assert {(edge.source, edge.target) for edge in graph.get_graph().edges} == {
        ("__start__", "coding_agent"),
        ("coding_agent", "__end__"),
    }
    assert graph.checkpointer is None
    assert graph.store is None


def test_shared_schemas_reuse_message_and_ui_reducers_without_parent_state():
    from src import coding_agent

    input_hints = get_type_hints(coding_agent.CoderInputState, include_extras=True)
    output_hints = get_type_hints(coding_agent.CoderOutputState, include_extras=True)
    state_hints = get_type_hints(coding_agent.CoderState, include_extras=True)

    assert get_args(input_hints["messages"])[1] is operator.add
    assert get_args(output_hints["messages"])[1] is operator.add
    assert get_args(state_hints["messages"])[1] is operator.add
    assert get_args(output_hints["ui"])[1] is ui_message_reducer
    assert get_args(state_hints["ui"])[1] is ui_message_reducer
    assert not ({"target_agent", "coding_task", "librarian_task"} & state_hints.keys())


@pytest.mark.parametrize(
    ("todos", "expected_status"),
    [
        ([], "completed"),
        ([{"content": "Waiting on input", "status": "pending"}], "blocked"),
    ],
)
def test_complete_graph_returns_only_shared_output_for_normal_results(
    monkeypatch, tmp_path, todos, expected_status
):
    result = _invoke_graph(monkeypatch, tmp_path, todos=todos)

    assert set(result) == _OUTPUT_FIELDS
    assert result["messages"][0]["content"] == "Do the work"
    assert result["messages"][-1].content.startswith("Completion report")
    assert result["workspace"] == str(tmp_path)
    assert result["execution_manifest"]["selected_repository"] == str(tmp_path)
    assert result["coding_session_id"].startswith("coding-v1-")
    assert result["coding_status"] == expected_status
    assert result["ui"] == []


def test_complete_graph_invalid_workspace_uses_shared_sanitized_error_output():
    from src import coding_agent

    result = asyncio.run(
        coding_agent.create_coding_agent_graph().ainvoke(
            {
                "messages": [{"role": "user", "content": "Inspect secret-path"}],
                "workspace": "secret-path",
                "thread_identity": "invalid-workspace",
            }
        )
    )

    assert set(result) <= _OUTPUT_FIELDS
    assert result["coding_status"] == "error"
    assert result["coding_session_id"] == ""
    assert "secret-path" not in result["messages"][-1].content
    assert "invalid_workspace" in result["messages"][-1].content


def test_complete_graph_internal_failure_uses_shared_sanitized_error_output(
    monkeypatch, tmp_path
):
    result = _invoke_graph(
        monkeypatch,
        tmp_path,
        error=RuntimeError("provider-secret-detail"),
    )

    assert set(result) <= _OUTPUT_FIELDS
    assert result["coding_status"] == "error"
    assert "provider-secret-detail" not in result["messages"][-1].content
    assert "agent_failure" in result["messages"][-1].content


@pytest.mark.parametrize(
    ("raw_mode", "read_only", "tool_names", "interrupt_names"),
    [
        (None, True, [], set()),
        ("unsupported", True, [], set()),
        (
            "approval",
            False,
            _MUTABLE_TOOL_NAMES,
            {
                "write_file",
                "edit_file",
                "delete",
                "execute",
                "custodian_compose_read",
                "custodian_github_publish",
            },
        ),
        (
            "autonomous",
            False,
            _MUTABLE_TOOL_NAMES,
            {"custodian_github_publish"},
        ),
    ],
)
def test_execution_mode_matrix_is_preserved(
    monkeypatch,
    tmp_path,
    raw_mode,
    read_only,
    tool_names,
    interrupt_names,
):
    from src import coding_agent

    captured = {}

    class TodoMiddleware:
        pass

    class Backend:
        def __init__(self, workspace, *, read_only):
            captured["backend"] = (workspace, read_only)

    def create_agent(**kwargs):
        captured["agent"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (TodoMiddleware, create_agent),
    )
    monkeypatch.setattr(coding_agent, "CustodianBackend", Backend)
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: object())
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)

    coding_agent._build_deep_agent(
        tmp_path,
        None,
        execution_mode=raw_mode,
    )

    assert captured["backend"] == (str(tmp_path), read_only)
    assert [tool.name for tool in captured["agent"]["tools"]] == tool_names
    assert set(captured["agent"]["interrupt_on"] or {}) == interrupt_names
    assert captured["agent"]["checkpointer"] is None
    assert captured["agent"]["permissions"] is None


def test_production_has_one_complete_coder_builder_and_no_direct_node_consumer():
    from src import coding_agent

    src_dir = Path(coding_agent.__file__).parent
    builder_definitions = []
    for path in src_dir.glob("*.py"):
        source = path.read_text()
        tree = ast.parse(source)
        if path.name != "coding_agent.py":
            assert "deep_agents_coding_node" not in source
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name == "create_coding_agent_graph"
            ):
                builder_definitions.append(path.name)

    assert builder_definitions == ["coding_agent.py"]
    assert "create_coding_agent_graph()" in (src_dir / "chat_ui.py").read_text()
