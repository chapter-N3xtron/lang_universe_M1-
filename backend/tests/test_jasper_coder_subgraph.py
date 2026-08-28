import inspect
from collections import OrderedDict
from typing import Any, get_args, get_origin, get_type_hints

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import PrivateAttr
from typing_extensions import TypedDict

from src import coding_agent, jasper_agent

MANIFEST = {
    "filesystem_origin": "native_custodian",
    "selected_repository": "/tmp",
    "command_runtime": "native_custodian_host",
    "host_worker": "unavailable",
}


class SequenceModel(BaseChatModel):
    _responses: list[AIMessage] = PrivateAttr()

    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)

    @property
    def _llm_type(self):
        return "jasper-coder-subgraph-test"

    def bind_tools(self, _tools, **_kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **_kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._responses.pop(0))])


def _request(tmp_path, mode="read_only"):
    return {
        "messages": [HumanMessage(content="Implement the requested change")],
        "workspace": str(tmp_path),
        "model": "ollama/test-model",
        "execution_mode": mode,
        "thread_identity": "jasper-coder-thread",
        "user_identity": "test-user",
        "coding_session_id": "existing-session",
    }


def _patch_coder(monkeypatch, captured):
    async def fake_coder(state, config=None):
        captured.append((dict(state), config))
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "execute",
                            "args": {"command": "pytest"},
                            "id": "internal-tool-call",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="internal transcript",
                    tool_call_id="internal-tool-call",
                ),
                AIMessage(content="Coder completed and verified the task."),
            ],
            "workspace": state["workspace"],
            "execution_manifest": {
                **MANIFEST,
                "selected_repository": state["workspace"],
            },
            "coding_session_id": "coding-session-1",
            "coding_status": "completed",
        }

    monkeypatch.setattr(coding_agent, "deep_agents_coding_node", fake_coder)


def _handoff(request):
    async def transfer(_state):
        return Command(
            goto="coder_bridge",
            update={"coding_request": request},
            graph=Command.PARENT,
        )

    child_builder = StateGraph(jasper_agent.JasperGraphState)
    child_builder.add_node("transfer", transfer)
    child_builder.add_edge(START, "transfer")
    child_builder.add_edge("transfer", END)
    child = child_builder.compile()

    async def call_jasper(state):
        return await child.ainvoke(state)

    return call_jasper


def test_bridge_declares_explicit_schemas_and_authoritative_local_subgraph():
    bridge = jasper_agent.create_jasper_coder_bridge()
    coder = bridge.builder.nodes["coder"].runnable
    hints = get_type_hints(jasper_agent.CoderBridgeState, include_extras=True)

    assert bridge.builder.input_schema is jasper_agent.CoderBridgeInputState
    assert bridge.builder.output_schema is jasper_agent.CoderBridgeOutputState
    assert set(bridge.get_input_jsonschema()["properties"]) == {"coding_request"}
    assert set(bridge.get_output_jsonschema()["properties"]) == {"coding_result"}
    assert set(bridge.get_graph().nodes) == {
        "__start__",
        "prepare_coder_input",
        "coder",
        "project_coder_output",
        "__end__",
    }
    assert coder.builder.state_schema is coding_agent.CoderState
    assert coder.checkpointer is None
    assert coder.store is None
    assert bridge.checkpointer is None
    assert bridge.store is None
    assert get_origin(hints["messages"]) is list
    assert get_args(hints["messages"]) == (Any,)
    source = inspect.getsource(jasper_agent.create_jasper_coder_bridge)
    assert ".ainvoke(" not in source
    assert "RemoteGraph" not in inspect.getsource(jasper_agent)


@pytest.mark.parametrize(
    "missing_field",
    [
        "messages",
        "workspace",
        "model",
        "execution_mode",
        "thread_identity",
        "user_identity",
        "coding_session_id",
    ],
)
def test_bridge_rejects_incomplete_requests(tmp_path, missing_field):
    request = _request(tmp_path)
    request.pop(missing_field)

    with pytest.raises(ValueError, match=f"coding_request {missing_field}"):
        jasper_agent._prepare_coder_input({"coding_request": request})


@pytest.mark.parametrize("messages", [[object()], [HumanMessage(content="")]])
def test_bridge_rejects_invalid_or_empty_delegated_messages(tmp_path, messages):
    request = _request(tmp_path)
    request["messages"] = messages

    with pytest.raises(ValueError, match="coding_request"):
        jasper_agent._prepare_coder_input({"coding_request": request})


@pytest.mark.parametrize("mode", ["read_only", "approval", "autonomous"])
@pytest.mark.asyncio
async def test_bridge_maps_exact_inputs_and_only_supported_final_output(
    monkeypatch, tmp_path, mode
):
    captured = []
    _patch_coder(monkeypatch, captured)
    request = _request(tmp_path, mode)
    authoritative = await coding_agent.create_coding_agent_graph().ainvoke(request)
    bridge = jasper_agent.create_jasper_coder_bridge()

    result = await bridge.ainvoke(
        {
            "coding_request": request,
            "jasper_response": "must not cross",
            "visual_artifacts": [{"must": "not cross"}],
        }
    )

    assert len(captured) == 2
    coder_input, _ = captured[1]
    assert set(coder_input) == {
        "messages",
        "workspace",
        "model",
        "execution_mode",
        "thread_identity",
        "user_identity",
        "coding_session_id",
        "ui",
    }
    assert len(coder_input["messages"]) == 1
    assert coder_input["messages"][0].content == "Implement the requested change"
    assert coder_input["workspace"] == str(tmp_path)
    assert coder_input["model"] == "ollama/test-model"
    assert coder_input["execution_mode"] == mode
    assert coder_input["thread_identity"] == "jasper-coder-thread"
    assert coder_input["user_identity"] == "test-user"
    assert coder_input["coding_session_id"] == "existing-session"

    assert set(result) == {"coding_result"}
    projected = result["coding_result"]
    assert set(projected) == {
        "messages",
        "workspace",
        "execution_manifest",
        "coding_session_id",
        "coding_status",
    }
    assert len(projected["messages"]) == 1
    assert projected["messages"][0].name == "coding"
    assert projected["messages"][0].content == "Coder completed and verified the task."
    assert "Implement the requested change" not in projected["messages"][0].content
    assert "internal transcript" not in projected["messages"][0].content
    assert projected["coding_status"] == authoritative["coding_status"]
    assert projected["coding_session_id"] == authoritative["coding_session_id"]
    assert projected["workspace"] == authoritative["workspace"]
    assert projected["execution_manifest"] == authoritative["execution_manifest"]
    assert projected["messages"][0].content == authoritative["messages"][-1].content


@pytest.mark.parametrize("mode", ["read_only", "approval", "autonomous"])
@pytest.mark.asyncio
async def test_embedded_mode_build_matches_authoritative_tool_policy(
    monkeypatch, tmp_path, mode
):
    captures = []

    class TodoMiddleware:
        pass

    class Backend:
        def __init__(self, workspace, *, read_only):
            self.workspace = workspace
            self.read_only = read_only

    class Agent:
        async def astream(self, payload, config=None, stream_mode=None):
            yield {
                "messages": [
                    *payload["messages"],
                    AIMessage(content="Coder completed the representative task."),
                ],
                "todos": [],
            }

    def create_agent(**kwargs):
        captures.append(
            {
                "tools": [tool.name for tool in kwargs["tools"]],
                "interrupts": set(kwargs["interrupt_on"] or {}),
                "checkpointer": kwargs["checkpointer"],
                "permissions": kwargs["permissions"],
                "read_only": kwargs["backend"].read_only,
            }
        )
        return Agent()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (TodoMiddleware, create_agent),
    )
    monkeypatch.setattr(coding_agent, "CustodianBackend", Backend)
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: object())
    monkeypatch.setattr(coding_agent, "_SESSION_AGENT_CACHE", OrderedDict())
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)

    coding_agent._build_deep_agent(tmp_path, None, execution_mode=mode)
    authoritative_policy = captures[-1]
    result = await jasper_agent.create_jasper_coder_bridge().ainvoke(
        {"coding_request": _request(tmp_path, mode)}
    )
    embedded_policy = captures[-1]

    assert embedded_policy == authoritative_policy
    assert embedded_policy["checkpointer"] is None
    assert embedded_policy["permissions"] is None
    if mode == "read_only":
        assert embedded_policy["tools"] == []
        assert embedded_policy["interrupts"] == set()
        assert embedded_policy["read_only"] is True
    elif mode == "approval":
        assert "execute" in embedded_policy["interrupts"]
        assert embedded_policy["read_only"] is False
    else:
        assert "execute" not in embedded_policy["interrupts"]
        assert embedded_policy["interrupts"] == {"custodian_github_publish"}
        assert embedded_policy["read_only"] is False
    assert result["coding_result"]["coding_status"] == "completed"
    assert result["coding_result"]["execution_manifest"]["selected_repository"] == str(
        tmp_path
    )


@pytest.mark.asyncio
async def test_embedded_sanitized_error_matches_authoritative_coder():
    request = {
        "messages": [HumanMessage(content="Inspect secret-path")],
        "workspace": "secret-path",
        "model": None,
        "execution_mode": "read_only",
        "thread_identity": "invalid-workspace",
        "user_identity": "test-user",
        "coding_session_id": "",
    }

    authoritative = await coding_agent.create_coding_agent_graph().ainvoke(request)
    embedded = await jasper_agent.create_jasper_coder_bridge().ainvoke(
        {"coding_request": request}
    )
    projected = embedded["coding_result"]

    assert projected["coding_status"] == authoritative["coding_status"] == "error"
    assert (
        projected["coding_session_id"]
        == authoritative["coding_session_id"]
        == "invalid-workspace"
    )
    assert projected["messages"][0].content == authoritative["messages"][-1].content
    assert "secret-path" not in projected["messages"][0].content
    assert "invalid_workspace" in projected["messages"][0].content


@pytest.mark.parametrize("status", ["completed", "blocked", "error"])
def test_jasper_boundary_preserves_coder_status(status):
    result = jasper_agent._coder_jasper_output(
        {
            "coding_result": {
                "messages": [
                    AIMessage(content=f"Coder status: {status}", name="coding")
                ],
                "coding_session_id": "coding-session-status",
                "coding_status": status,
            }
        }
    )

    assert result["jasper_result"]["route"] == "record_session"
    assert result["jasper_result"]["coding_status"] == status
    assert result["jasper_result"]["messages"][0]["name"] == "coding"


@pytest.mark.asyncio
async def test_jasper_command_enters_local_bridge_and_returns_coder_result(
    monkeypatch, tmp_path
):
    captured = []
    request = _request(tmp_path)
    _patch_coder(monkeypatch, captured)
    monkeypatch.setattr(jasper_agent, "call_jasper", _handoff(request))

    graph = jasper_agent.create_jasper_graph()
    result = await graph.ainvoke(
        {
            "jasper_request": {
                "messages": [{"role": "user", "content": "Use Coding"}],
                "workspace": str(tmp_path),
                "execution_mode": "read_only",
                "thread_identity": "jasper-coder-thread",
                "user_identity": "test-user",
            }
        }
    )

    assert captured
    assert result["jasper_result"]["route"] == "record_session"
    assert result["jasper_result"]["coding_status"] == "completed"
    assert result["jasper_result"]["messages"] == [
        {
            "role": "assistant",
            "content": "Coder completed and verified the task.",
            "name": "coding",
        }
    ]


class ParentState(TypedDict, total=False):
    jasper_request: dict
    jasper_result: dict


def _parent_graph():
    graph = StateGraph(ParentState)
    graph.add_node("jasper", jasper_agent.create_jasper_graph())
    graph.add_edge(START, "jasper")
    graph.add_edge("jasper", END)
    return graph


@pytest.mark.asyncio
async def test_parent_only_checkpointer_restores_nested_interrupt(
    monkeypatch, tmp_path
):
    from deepagents.backends import FilesystemBackend

    request = _request(tmp_path, "approval")
    model = SequenceModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": "/durable.txt",
                            "content": "persisted",
                        },
                        "id": "nested-approved-write",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Coder completed the approved write."),
        ]
    )
    monkeypatch.setattr(coding_agent, "_SESSION_AGENT_CACHE", OrderedDict())
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model)
    monkeypatch.setattr(
        coding_agent,
        "CustodianBackend",
        lambda workspace, read_only: FilesystemBackend(
            root_dir=workspace, virtual_mode=True
        ),
    )
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)
    monkeypatch.setattr(jasper_agent, "call_jasper", _handoff(request))
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "jasper-coder-thread"}}

    first = _parent_graph().compile(checkpointer=saver)
    initial = await first.ainvoke(
        {
            "jasper_request": {
                "messages": [{"role": "user", "content": "Use Coding"}],
                "workspace": str(tmp_path),
                "execution_mode": "approval",
                "thread_identity": "jasper-coder-thread",
                "user_identity": "test-user",
            }
        },
        config=config,
    )
    snapshot = first.get_state(config, subgraphs=True)
    jasper_task = snapshot.tasks[0]
    bridge_task = jasper_task.state.tasks[0]
    coder_task = bridge_task.state.tasks[0]
    coding_task = coder_task.state.tasks[0]

    assert "__interrupt__" in initial
    assert jasper_task.name == "jasper"
    assert bridge_task.name == "coder_bridge"
    assert coder_task.name == "coder"
    assert coding_task.name == "coding_agent"
    assert jasper_task.interrupts == bridge_task.interrupts
    assert bridge_task.interrupts == coder_task.interrupts
    assert "jasper:" in coder_task.state.config["configurable"]["checkpoint_ns"]
    assert "coder_bridge:" in coder_task.state.config["configurable"]["checkpoint_ns"]
    assert "coder:" in coder_task.state.config["configurable"]["checkpoint_ns"]

    restored = _parent_graph().compile(checkpointer=saver)
    result = await restored.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config=config
    )

    assert result["jasper_result"]["coding_status"] == "completed"
    assert result["jasper_result"]["coding_session_id"] == "jasper-coder-thread"
    assert (
        "Coder completed the approved write."
        in result["jasper_result"]["messages"][0]["content"]
    )
    assert (tmp_path / "durable.txt").read_text() == "persisted"
    assert jasper_agent.create_jasper_graph().checkpointer is None


def test_outer_graph_registers_compiled_jasper_without_coding_sibling():
    from langgraph.graph.state import CompiledStateGraph

    from src.chat_ui import create_chat_ui

    outer = create_chat_ui()
    jasper = outer.nodes["jasper"].runnable

    assert isinstance(jasper, CompiledStateGraph)
    assert "coding" not in outer.nodes
    assert jasper.checkpointer is None
    assert jasper.store is None
