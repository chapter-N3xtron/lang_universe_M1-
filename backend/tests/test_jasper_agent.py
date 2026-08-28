"""Tests for Jasper's LangChain agent wrapper and deterministic fallbacks."""

import asyncio
import importlib
import json
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
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
    src_package = sys.modules.get("src")
    for key in ("src.jasper_agent", "src.llm"):
        sys.modules.pop(key, None)
        if src_package is not None:
            module_name = key.rsplit(".", 1)[-1]
            if hasattr(src_package, module_name):
                delattr(src_package, module_name)


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
    assert "exact selected repository through native Custodian" in prompt
    assert "read_host_file" in prompt
    assert "direct Custodian worker" in prompt


@pytest.mark.asyncio
async def test_jasper_text_strategy_produces_canonical_assistant_message():
    model = _plain_model(AIMessage(content="Hello! I can help with daily tasks."))

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = await module.call_jasper(
            {"messages": [{"role": "user", "content": "What can you do?"}]}
        )

    assert len(result["messages"]) == 1
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
        result = await module.call_jasper(
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
        result = await module.call_jasper(
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
        result = await module.call_jasper(
            {"messages": [{"role": "user", "content": "Explain this"}]}
        )

    assert result["jasper_response"] == "Here is the recovered final answer."
    assert "No-Self rule" in module.NO_SELF_RESPONSE_GUIDANCE
    assert "unrequested next steps" in module.NO_SELF_RESPONSE_GUIDANCE


def test_jasper_docker_handoff_uses_direct_custodian_route():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    prompt = " ".join(module.SYSTEM_PROMPT.split())
    assert "Docker, Docker Compose, or other host-side changes" in prompt
    assert "direct Custodian worker" in prompt
    assert "do not replace the requested outcome with a preflight" in prompt


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
        result = await module.call_jasper(
            {"messages": [{"role": "user", "content": "What are my todos?"}]}
        )

    assert len(result["messages"]) == 1
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
        result = await module.call_jasper(
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
        result = await module.call_jasper(
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


def test_host_file_notice_precedes_token_bound_read():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    client = MagicMock()
    client.action.side_effect = [
        {
            "ok": True,
            "path": "/Users/chapter/Documents/notes.txt",
            "reason": "Read the notes requested by the human.",
            "notice_token": "one-use-token",
        },
        {"ok": True, "content": "ordinary notes"},
    ]

    with (
        patch.object(module, "_host_file_client", return_value=client),
        patch.object(module, "push_ui_message") as push_notice,
    ):
        notice = module.announce_host_file_read.invoke(
            {
                "path": "/Users/chapter/Documents/notes.txt",
                "reason": "Read the notes requested by the human.",
            }
        )
        result = module.read_host_file.invoke({**notice, "max_chars": 12000})

    assert client.action.call_args_list == [
        call(
            "preflight_host_file",
            path="/Users/chapter/Documents/notes.txt",
            reason="Read the notes requested by the human.",
        ),
        call(
            "read_host_file",
            path="/Users/chapter/Documents/notes.txt",
            reason="Read the notes requested by the human.",
            notice_token="one-use-token",
            max_chars=12000,
        ),
    ]
    push_notice.assert_called_once_with(
        "host_file_notice",
        {
            "path": "/Users/chapter/Documents/notes.txt",
            "reason": "Read the notes requested by the human.",
        },
        state_key="ui",
    )
    assert result == "ordinary notes"


def test_jasper_delegates_web_access_to_librarian_without_direct_web_tools():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    specialists = module._specialists(MagicMock())

    assert specialists == []
    assert [tool.name for tool in module.ACTIVE_TOOLS] == [
        "list_todos",
        "read_repository_file",
        "announce_host_file_read",
        "read_host_file",
        "draw_concept_map",
        "transfer_to_coding",
        "transfer_to_librarian",
        "transfer_to_ocr",
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
        "announce_host_file_read",
        "read_host_file",
        "read_repository_file",
        "task",
        "transfer_to_coding",
        "transfer_to_librarian",
        "transfer_to_ocr",
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
    assert create_agent.call_args.kwargs["permissions"] is None
    assert create_agent.call_args.kwargs["backend"].read_only is True


def test_jasper_handoff_targets_local_coder_bridge_with_required_context(tmp_path):
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
    assert command.goto == "coder_bridge"
    request = command.update["coding_request"]
    assert request["workspace"] == str(tmp_path)
    assert request["execution_mode"] == "approval"
    assert request["thread_identity"] == "top-level-coding-test"
    assert request["user_identity"] == "test-user"
    assert request["messages"][0].content == "Inspect the repository"
    assert len(command.update["messages"]) == 2
    assert command.update["messages"][1].tool_call_id == "coding-handoff-1"


def test_real_jasper_tool_handoff_enters_local_coder_subgraph(tmp_path):
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    coding_module = importlib.import_module("src.coding_agent")
    model = _plain_model(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "transfer_to_coding",
                    "args": {"task": "Inspect the repository"},
                    "id": "real-coding-handoff",
                    "type": "tool_call",
                }
            ],
        )
    )
    captured = []

    async def fake_coder(state, config=None):
        captured.append((state, config))
        return {
            "messages": [AIMessage(content="Coder completed the inspection.")],
            "workspace": state["workspace"],
            "coding_session_id": "coding-session-real-handoff",
            "coding_status": "completed",
        }

    with (
        patch.object(module, "get_agent_llm", return_value=model),
        patch.object(module, "select_response_strategy", return_value="text"),
        patch.object(coding_module, "deep_agents_coding_node", fake_coder),
    ):
        graph = module.create_jasper_graph()
        result = asyncio.run(
            graph.ainvoke(
                {
                    "jasper_request": {
                        "messages": [
                            {"role": "user", "content": "Use Coding to inspect this"}
                        ],
                        "workspace": str(tmp_path),
                        "model": "ollama/test-model",
                        "execution_mode": "read_only",
                        "thread_identity": "real-handoff-thread",
                        "user_identity": "test-user",
                    }
                }
            )
        )

    assert captured[0][0]["messages"][0].content == "Inspect the repository"
    assert result["jasper_result"]["coding_status"] == "completed"
    assert result["jasper_result"]["messages"][-1]["name"] == "coding"


def test_jasper_autonomous_handoff_targets_local_coder_bridge(tmp_path):
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
    assert command.goto == "coder_bridge"
    request = command.update["coding_request"]
    assert request["messages"][0].content == "Implement OpenSpec change example"
    assert request["execution_mode"] == "autonomous"


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


def test_jasper_handoff_targets_local_librarian_exit_with_bounded_context(tmp_path):
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
    assert command.goto == "librarian_exit"
    assert command.update["librarian_task"] == "Research SIFT"
    assert command.update["session_evidence"] == [{"id": "source-one"}]
    assert len(command.update["messages"]) == 2


@pytest.mark.asyncio
async def test_jasper_allows_local_handoff_command_to_reach_wrapper_graph():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    from langgraph.errors import ParentCommand
    from langgraph.types import Command

    parent_command = ParentCommand(Command(goto="coder_bridge", graph=Command.PARENT))
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


def test_jasper_graph_declares_local_coder_bridge():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")

    graph = module.create_jasper_graph()

    assert "coder_bridge" in graph.get_graph().nodes
    assert "coding" not in graph.get_graph().nodes
    assert graph.checkpointer is None
    assert graph.store is None


def test_jasper_deep_agent_executes_builtin_repository_discovery(monkeypatch, tmp_path):
    module = importlib.import_module("src.jasper_agent")
    from deepagents.backends import FilesystemBackend

    monkeypatch.setattr(
        module,
        "CustodianBackend",
        lambda workspace, read_only: FilesystemBackend(
            root_dir=workspace, virtual_mode=True
        ),
    )
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
