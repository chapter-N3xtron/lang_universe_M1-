"""Tests for Jasper's LangChain agent wrapper and deterministic fallbacks."""

import importlib
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import START, StateGraph
from pydantic import PrivateAttr

from src.visual_models import (
    ConceptMapArtifact,
    ConceptMapEdge,
    ConceptMapNode,
    ConceptMapPayload,
    EvidenceSource,
    JasperResponse,
)

EVIDENCE = EvidenceSource(
    id="user-input",
    kind="user_input",
    locator="current-user-message",
    title="Current user request",
    content_sha256="b" * 64,
)


def _grounded_node(node_id: str, label: str) -> ConceptMapNode:
    return ConceptMapNode(
        id=node_id,
        label=label,
        narration=f"Explanation of {label}.",
        claim_status="user_defined",
        evidence_refs=[EVIDENCE.id],
    )


def _grounded_edge(source: str, target: str) -> ConceptMapEdge:
    return ConceptMapEdge(
        source=source,
        target=target,
        claim_status="user_defined",
        evidence_refs=[EVIDENCE.id],
    )


def _clear_src_modules():
    for key in ("src.jasper_agent", "src.llm"):
        sys.modules.pop(key, None)


class _TestChatModel(BaseChatModel):
    _responses: list[AIMessage] = PrivateAttr()
    _bind_error: Exception | None = PrivateAttr()

    def __init__(self, responses=(), *, tool_calling=True, bind_error=None):
        super().__init__(profile={"tool_calling": tool_calling})
        self._responses = list(responses)
        self._bind_error = bind_error

    @property
    def _llm_type(self):
        return "jasper-test"

    def bind_tools(self, _tools, **_kwargs):
        if self._bind_error is not None:
            raise self._bind_error
        return self

    def _generate(self, _messages, stop=None, run_manager=None, **_kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._responses.pop(0))])


def _plain_model(*responses: AIMessage) -> _TestChatModel:
    return _TestChatModel(responses)


def test_jasper_prompt_contains_versioned_interaction_governance():
    _clear_src_modules()
    jasper_agent = importlib.import_module("src.jasper_agent")
    prompt = " ".join(jasper_agent.SYSTEM_PROMPT.split())

    assert jasper_agent.JASPER_INTERACTION_GOVERNANCE_VERSION == "2026-08-04.1"
    assert "strict No-Self rule" in prompt
    assert "The human controls pace, direction, and depth" in prompt
    assert "Do not interpret silence, inaction, or ambiguity as consent" in prompt
    assert "Prompt guidance does not replace any required LangGraph interrupt" in prompt
    assert "Hello. This system is called Jasper" in prompt
    assert "approximately 120 words" in prompt
    assert "no more than two short paragraphs" in prompt
    assert "authorize The Librarian" in prompt
    assert "Do not invent a standard or propose speculative coding" in prompt
    assert "model estimate, not an empirically calibrated probability" in prompt
    assert "Never search a parent, child, or sibling" in prompt
    assert "Linux Agent Server container" in prompt
    assert "request_macos_host_operation" in prompt
    assert "For Docker or Docker Compose work" in prompt
    assert "never use Mac inspection as a Docker preflight" in prompt


@pytest.mark.asyncio
async def test_jasper_text_strategy_produces_canonical_assistant_message():
    model = _plain_model(AIMessage(content="Hello! I can help with daily tasks."))

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "What can you do?"}]}
        )

    assert len(result["messages"]) == 2
    assert result["messages"][-1].content.startswith("Hello")
    assert result["jasper_response"] == result["messages"][-1].content
    assert result["visual_artifacts"] == []
    assert result["jasper_strategy"] == "text"


@pytest.mark.asyncio
async def test_jasper_provider_error_is_sanitized():
    model = _TestChatModel(
        bind_error=httpx.ConnectError(
            "secret provider detail",
            request=httpx.Request("POST", "https://ollama.com/api/chat"),
        )
    )

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "Test error handling"}]}
        )

    content = result["messages"][-1].content
    assert "selected model" in content
    assert not content.startswith("I ")
    assert "secret provider detail" not in content
    assert result["jasper_diagnostic"]["code"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_jasper_internal_error_is_not_misreported_as_provider_failure():
    model = _TestChatModel(bind_error=RuntimeError("internal agent failure"))

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "Test agent handling"}]}
        )

    assert "model responded" in result["messages"][-1].content
    assert result["jasper_diagnostic"]["code"] == "structured_output_invalid"


def test_bad_request_is_not_misreported_as_provider_failure():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    bad_request_type = type("BadRequestError", (Exception,), {})
    error = bad_request_type("invalid message history")
    error.__cause__ = httpx.HTTPStatusError(
        "400 Bad Request",
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        response=httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        ),
    )

    assert module._is_provider_failure(error) is False


@pytest.mark.asyncio
async def test_jasper_recovers_when_tool_loop_returns_empty_final_content():
    model = _plain_model(
        AIMessage(content=""),
        AIMessage(content="Here is the recovered final answer."),
    )

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "Explain this"}]}
        )

    assert result["jasper_response"] == "Here is the recovered final answer."
    assert "No-Self rule" in module.NO_SELF_RESPONSE_GUIDANCE
    assert "unrequested next steps" in module.NO_SELF_RESPONSE_GUIDANCE


def test_jasper_docker_handoff_uses_only_typed_sandbox_route():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    prompt = " ".join(module.SYSTEM_PROMPT.split())
    assert "exactly one typed docker_sandbox action" in prompt
    assert "request_docker_compose_operation" not in prompt
    assert "do not replace the requested deployment with a preflight" in prompt
    assert "typed host-operation interrupt remains the authority boundary" in prompt
    assert "preserve that separation" in prompt


@pytest.mark.asyncio
async def test_jasper_plain_agent_executes_tools_but_exposes_only_canonical_answer():
    model = _plain_model(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "list_todos",
                    "args": {},
                    "id": "call_test_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Here is your todo list summary."),
    )

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "What are my todos?"}]}
        )

    assert len(result["messages"]) == 2
    assert result["jasper_response"] == "Here is your todo list summary."


@pytest.mark.asyncio
async def test_text_strategy_does_not_bind_tools_for_incompatible_models():
    model = MagicMock()
    model.profile = {"tool_calling": False}
    captured = {}

    class TextAgent:
        async def ainvoke(self, _state):
            return {"messages": [AIMessage(content="A safe text-only answer.")]}

    def build_agent(
        _model,
        response_format=None,
        *,
        tools=None,
        workspace=None,
        execution_mode=None,
    ):
        captured["response_format"] = response_format
        captured["tools"] = tools
        captured["workspace"] = workspace
        captured["execution_mode"] = execution_mode
        return TextAgent()

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with patch.object(module, "_build_agent", side_effect=build_agent):
        result = await module._invoke_text(
            model, [{"role": "user", "content": "Answer in text"}]
        )

    assert result.voice_text == "A safe text-only answer."
    assert captured["tools"] == []


@pytest.mark.asyncio
async def test_two_pass_openai_uses_sanitized_native_schema():
    model = MagicMock(profile={"tool_calling": True})
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value={"voice_text": "The useful plain answer."}
    )

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with (
        patch.object(module, "_is_openai_model", return_value=True),
        patch.object(
            module,
            "_invoke_plain",
            new=AsyncMock(
                return_value=(
                    [AIMessage(content="The useful plain answer.")],
                    "The useful plain answer.",
                )
            ),
        ),
    ):
        result = await module._invoke_two_pass(
            model, [{"role": "user", "content": "Explain this"}]
        )

    assert result.voice_text == "The useful plain answer."
    schema = model.with_structured_output.call_args.args[0]
    kwargs = model.with_structured_output.call_args.kwargs
    assert kwargs == {"method": "json_schema", "strict": True}
    assert "oneOf" not in json.dumps(schema)
    assert "discriminator" not in json.dumps(schema)


@pytest.mark.asyncio
async def test_two_pass_format_failure_preserves_the_plain_answer():
    model = MagicMock(profile={"tool_calling": True})
    formatter = MagicMock()
    formatter.ainvoke = AsyncMock(side_effect=ValueError("invalid structured response"))
    model.with_structured_output.return_value = formatter

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "auto"}),
        patch.object(module, "get_agent_llm", return_value=model),
        patch.object(
            module,
            "_invoke_plain",
            new=AsyncMock(
                return_value=(
                    [AIMessage(content="The useful plain answer.")],
                    "The useful plain answer.",
                )
            ),
        ),
    ):
        result = await module.create_jasper_graph().ainvoke(
            {
                "messages": [{"role": "user", "content": "Explain this"}],
                "model": "ollama/unknown-model",
            }
        )

    assert result["jasper_strategy"] == "two_pass"
    assert result["jasper_response"] == "The useful plain answer."
    assert result["visual_artifacts"] == []
    assert result["jasper_diagnostic"]["code"] == "structured_output_invalid"


def _concept_map(title: str = "Request flow") -> ConceptMapArtifact:
    return ConceptMapArtifact(
        artifact_id="request-flow",
        title=title,
        alt_text="A request flows through Jasper, LangGraph, and the UI.",
        payload=ConceptMapPayload(
            grounding_kind="user_input",
            sources=[EVIDENCE],
            nodes=[
                _grounded_node("jasper", "Jasper"),
                _grounded_node("graph", "LangGraph"),
                _grounded_node("ui", "UI"),
            ],
            edges=[
                _grounded_edge("jasper", "graph"),
                _grounded_edge("graph", "ui"),
            ],
            narration_order=["jasper", "graph", "ui"],
        ),
    )


@pytest.mark.asyncio
async def test_two_pass_recovers_validated_tool_artifact_when_formatter_fails():
    module = importlib.import_module("src.jasper_agent")
    artifact = _concept_map()
    evidence = [
        ToolMessage(
            name="draw_concept_map",
            tool_call_id="draw-1",
            content=json.dumps(artifact.model_dump(mode="json")),
        )
    ]
    model = MagicMock()
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        side_effect=ValueError("invalid structured response")
    )

    with patch.object(
        module, "_invoke_plain", new=AsyncMock(return_value=(evidence, ""))
    ):
        result = await module._invoke_two_pass(
            model, [{"role": "user", "content": "Draw"}]
        )

    assert result.voice_text == 'The "Request flow" concept map is ready.'
    assert [item.artifact_id for item in result.artifacts] == ["request-flow"]
    assert result.layout_suggestion.mode == "split"
    assert result.diagnostic.code == "structured_output_invalid"


@pytest.mark.asyncio
async def test_two_pass_uses_tool_artifacts_instead_of_formatter_inventions():
    module = importlib.import_module("src.jasper_agent")
    artifact = _concept_map()
    invented = _concept_map("Invented map").model_copy(
        update={"artifact_id": "invented-map"}
    )
    evidence = [
        ToolMessage(
            name="draw_concept_map",
            tool_call_id="draw-1",
            content=json.dumps(artifact.model_dump(mode="json")),
        )
    ]
    model = MagicMock()
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=JasperResponse(
            voice_text="Here is the request flow.",
            artifacts=[invented],
        )
    )

    with patch.object(
        module, "_invoke_plain", new=AsyncMock(return_value=(evidence, ""))
    ):
        result = await module._invoke_two_pass(
            model, [{"role": "user", "content": "Draw"}]
        )

    assert [item.artifact_id for item in result.artifacts] == ["request-flow"]


@pytest.mark.asyncio
async def test_combined_strategy_drops_artifacts_not_returned_by_visual_tool():
    module = importlib.import_module("src.jasper_agent")
    invented = _concept_map("Invented map")
    agent = MagicMock()
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [AIMessage(content="An unsupported diagram.")],
            "structured_response": {
                "version": 2,
                "voice_text": "An unsupported diagram.",
                "artifacts": [invented.model_dump(mode="json")],
            },
        }
    )

    with patch.object(module, "_build_agent", return_value=agent):
        result = await module._invoke_combined(
            MagicMock(), [{"role": "user", "content": "Draw"}], "tool"
        )

    assert result.artifacts == []
    assert result.layout_suggestion is None


@pytest.mark.asyncio
async def test_combined_strategy_associates_artifact_with_canonical_message():
    artifact = ConceptMapArtifact(
        artifact_id="map-one",
        title="One to two",
        alt_text="One flows to two.",
        payload=ConceptMapPayload(
            grounding_kind="user_input",
            sources=[EVIDENCE],
            nodes=[
                _grounded_node("one", "One"),
                _grounded_node("two", "Two"),
            ],
            edges=[_grounded_edge("one", "two")],
            narration_order=["one", "two"],
        ),
    )
    structured = JasperResponse(
        voice_text="One flows to two.",
        artifacts=[artifact],
    )

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "tool"}),
        patch.object(module, "get_agent_llm", return_value=MagicMock()),
        patch.object(
            module, "_invoke_combined", new=AsyncMock(return_value=structured)
        ),
    ):
        result = await module.create_jasper_graph().ainvoke(
            {"messages": [{"role": "user", "content": "Draw the flow"}]}
        )

    message = result["messages"][-1]
    assert result["visual_artifacts"][0]["source_message_id"] == message.id
    assert result["jasper_structured_response"]["voice_text"] == message.content
    assert result["jasper_strategy"] == "tool"


def test_strategy_is_conservative_without_verified_combined_capability():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    unknown = MagicMock(profile=None)
    assert module.select_response_strategy(unknown, "ollama/example") == "two_pass"

    no_tools = MagicMock(profile={"tool_calling": False})
    assert module.select_response_strategy(no_tools) == "text"

    native = MagicMock(
        profile={
            "tool_calling": True,
            "structured_output": True,
            "structured_output_with_tools": True,
        }
    )
    assert module.select_response_strategy(native) == "native"


def test_invalid_strategy_override_falls_back_to_auto(monkeypatch):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    monkeypatch.setenv("JASPER_STRUCTURED_STRATEGY", "not-a-strategy")
    assert module.select_response_strategy(MagicMock(profile=None)) == "two_pass"


def test_exact_verified_model_override_is_used(monkeypatch):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    monkeypatch.setitem(
        module.VERIFIED_MODEL_CAPABILITIES,
        "ollama/tested-model",
        module.VerifiedModelCapability(
            strategy="tool",
            verified_at="2026-07-30",
            evidence="live combined structured-output test",
        ),
    )
    assert (
        module.select_response_strategy(MagicMock(profile=None), "ollama/tested-model")
        == "tool"
    )
    assert (
        module.select_response_strategy(MagicMock(profile=None), "ollama/not-tested")
        == "two_pass"
    )


def test_jasper_delegates_web_access_to_librarian_without_direct_web_tools():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    specialists = module._specialists(MagicMock())

    assert specialists == []
    assert [tool.name for tool in module.ACTIVE_TOOLS] == [
        "list_todos",
        "read_repository_file",
        "draw_concept_map",
        "transfer_to_coding",
        "transfer_to_librarian",
    ]


def test_jasper_deep_agent_exposes_documented_tools_and_task(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    model = _plain_model(AIMessage(content="done"))
    agent = module._build_agent(model, workspace=str(tmp_path))
    tool_names = set(agent.nodes["tools"].bound.tools_by_name)

    assert tool_names == {
        "draw_concept_map",
        "glob",
        "grep",
        "list_todos",
        "ls",
        "read_file",
        "read_repository_file",
        "task",
        "transfer_to_coding",
        "transfer_to_librarian",
    }
    assert tool_names.isdisjoint({"web_search", "read_url", "ingest_uploaded_sources"})


@pytest.mark.parametrize("execution_mode", [None, "read_only", "autonomous"])
def test_jasper_mutation_tools_are_hidden_outside_approval_mode(
    tmp_path, execution_mode
):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    agent = module._build_agent(
        _plain_model(AIMessage(content="done")),
        workspace=str(tmp_path),
        execution_mode=execution_mode,
    )
    tool_names = set(agent.nodes["tools"].bound.tools_by_name)

    assert tool_names.isdisjoint(
        {"approved_write_file", "approved_edit_file", "run_workspace_command"}
    )


def test_jasper_mutation_tools_are_exposed_in_approval_mode(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    agent = module._build_agent(
        _plain_model(AIMessage(content="done")),
        workspace=str(tmp_path),
        execution_mode="approval",
    )
    tool_names = set(agent.nodes["tools"].bound.tools_by_name)

    assert {
        "approved_write_file",
        "approved_edit_file",
        "run_workspace_command",
    } <= tool_names


def test_jasper_approval_mode_uses_human_review_interrupts(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    with patch.object(module, "create_deep_agent") as create_agent:
        module._build_agent(
            _plain_model(AIMessage(content="done")),
            workspace=str(tmp_path),
            execution_mode="approval",
        )

    assert create_agent.call_args.kwargs["interrupt_on"] == module.APPROVAL_INTERRUPT_ON


def test_jasper_handoff_targets_top_level_coding_with_required_context(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    runtime = MagicMock(
        tool_call_id="coding-handoff-1",
        state={
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "transfer_to_coding",
                            "args": {"task": "Inspect the repository"},
                            "id": "coding-handoff-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "workspace": str(tmp_path),
            "model": "ollama/test-model",
            "execution_mode": "approval",
            "thread_identity": "top-level-coding-test",
            "user_identity": "test-user",
        },
    )
    command = module.transfer_to_coding.func(
        task="Inspect the repository", runtime=runtime
    )

    assert command.graph == command.PARENT
    assert command.goto == "coding"
    assert command.update["workspace"] == str(tmp_path)
    assert command.update["execution_mode"] == "approval"
    assert command.update["thread_identity"] == "top-level-coding-test"
    assert len(command.update["messages"]) == 2
    assert command.update["messages"][1].tool_call_id == "coding-handoff-1"


def test_jasper_autonomous_handoff_targets_top_level_coding(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    runtime = MagicMock(
        tool_call_id="coding-handoff-autonomous",
        state={
            "messages": [AIMessage(content="", tool_calls=[])],
            "workspace": str(tmp_path),
            "model": "ollama/test-model",
            "execution_mode": "autonomous",
            "thread_identity": "autonomous-coding-test",
        },
    )

    command = module.transfer_to_coding.func(
        task="Implement OpenSpec change example", runtime=runtime
    )

    assert command.graph == command.PARENT
    assert command.goto == "coding"
    assert command.update["coding_task"] == "Implement OpenSpec change example"
    assert command.update["pending_agent"] == ""
    assert command.update["pending_approval"] is False
    assert command.update["execution_mode"] == "autonomous"


def test_jasper_handoff_requires_explicit_execution_mode(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    runtime = MagicMock(
        tool_call_id="coding-handoff-2",
        state={
            "messages": [AIMessage(content="", tool_calls=[])],
            "workspace": str(tmp_path),
        },
    )

    with pytest.raises(ValueError, match="Select read_only, approval, or autonomous"):
        module.transfer_to_coding.func(task="Inspect", runtime=runtime)


def test_jasper_handoff_targets_top_level_librarian_with_bounded_context(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    runtime = MagicMock(
        tool_call_id="librarian-handoff-1",
        state={
            "messages": [AIMessage(content="", tool_calls=[])],
            "workspace": str(tmp_path),
            "model": "ollama/test-model",
            "thread_identity": "librarian-thread",
            "user_identity": "test-user",
            "session_evidence": [{"id": "source-one"}],
        },
    )

    command = module.transfer_to_librarian.func(task="Research SIFT", runtime=runtime)

    assert command.graph == command.PARENT
    assert command.goto == "librarian"
    assert command.update["librarian_task"] == "Research SIFT"
    assert command.update["session_evidence"] == [{"id": "source-one"}]
    assert len(command.update["messages"]) == 2


@pytest.mark.asyncio
async def test_jasper_allows_parent_handoff_command_to_reach_outer_graph():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    from langgraph.errors import ParentCommand
    from langgraph.types import Command

    parent_command = ParentCommand(Command(goto="coding", graph=Command.PARENT))
    with (
        patch.object(module, "get_agent_llm", return_value=MagicMock(profile={})),
        patch.object(module, "select_response_strategy", return_value="text"),
        patch.object(module, "_invoke_text", side_effect=parent_command),
        pytest.raises(ParentCommand),
    ):
        await module.call_jasper(
            {
                "messages": [{"role": "user", "content": "Use Coding"}],
                "execution_mode": "read_only",
            }
        )


@pytest.mark.asyncio
async def test_documented_handoff_tool_runs_top_level_coding_node(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    model = _plain_model(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "transfer_to_coding",
                    "args": {"task": "Read the selected workspace"},
                    "id": "top-level-handoff-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Jasper relayed the Coding result."),
    )
    jasper = module._build_agent(model, workspace=str(tmp_path))
    coding_inputs = []

    async def run_jasper(state, config):
        return await jasper.ainvoke(state, config=config)

    async def run_coding(state):
        coding_inputs.append(state)
        return {"messages": [AIMessage(content="TOP_LEVEL_CODING_OK")]}

    graph = StateGraph(module.JasperDeepAgentState)
    graph.add_node("jasper", run_jasper)
    graph.add_node("coding", run_coding)
    graph.add_edge(START, "jasper")
    graph.add_edge("coding", "jasper")
    result = await graph.compile().ainvoke(
        {
            "messages": [{"role": "user", "content": "Use Coding"}],
            "workspace": str(tmp_path),
            "execution_mode": "read_only",
            "thread_identity": "documented-handoff-test",
        }
    )

    assert coding_inputs
    assert coding_inputs[0]["coding_task"] == "Read the selected workspace"
    assert coding_inputs[0]["workspace"] == str(tmp_path)
    assert coding_inputs[0]["execution_mode"] == "read_only"
    assert result["messages"][-1].content == "Jasper relayed the Coding result."


def test_jasper_deep_agent_executes_builtin_repository_discovery(tmp_path):
    module = importlib.import_module("src.jasper_agent")
    (tmp_path / "README.md").write_text("repository evidence")
    model = _plain_model(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "ls",
                    "args": {"path": "/"},
                    "id": "ls-repository-root",
                }
            ],
        ),
        AIMessage(content="Repository inspected."),
    )

    result = module._build_agent(model, workspace=str(tmp_path)).invoke(
        {
            "messages": [{"role": "user", "content": "Inspect the repository."}],
            "workspace": str(tmp_path),
        }
    )

    tool_result = result["messages"][-2]
    assert isinstance(tool_result, ToolMessage)
    assert tool_result.name == "ls"
    assert "README.md" in tool_result.content
    assert result["messages"][-1].content == "Repository inspected."


def test_jasper_returns_tool_validation_failures_to_model_for_correction():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    retry = next(
        middleware
        for middleware in module._middleware()
        if type(middleware).__name__ == "ToolRetryMiddleware"
    )

    assert retry.max_retries == 1
    assert retry.on_failure == "continue"


def test_jasper_prompt_names_the_stable_user_input_evidence_id():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    assert 'exact evidence ID "user-input"' in module.SYSTEM_PROMPT
    assert 'stable evidence ID "user-input"' in module.draw_concept_map.description


@pytest.mark.asyncio
async def test_second_visual_request_returns_the_new_tool_artifact():
    module = importlib.import_module("src.jasper_agent")
    previous = _concept_map("Previous scientific method map")
    current = _concept_map("New SIFT map").model_copy(
        update={"artifact_id": "sift-map"}
    )
    evidence = [
        ToolMessage(
            name="draw_concept_map",
            tool_call_id="draw-sift",
            content=json.dumps(current.model_dump(mode="json")),
        )
    ]
    model = MagicMock()
    model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=JasperResponse(
            voice_text="Here is the SIFT map.",
            artifacts=[current],
        )
    )
    history = [
        {"role": "user", "content": "Draw the scientific method."},
        {"role": "assistant", "content": previous.title},
        {"role": "user", "content": "Now add a SIFT visualization."},
    ]

    with patch.object(
        module, "_invoke_plain", new=AsyncMock(return_value=(evidence, "Done"))
    ):
        result = await module._invoke_two_pass(model, history)

    assert [artifact.artifact_id for artifact in result.artifacts] == ["sift-map"]
