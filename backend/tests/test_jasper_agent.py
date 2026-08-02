"""Tests for Jasper's LangChain agent wrapper and deterministic fallbacks."""

import importlib
import json
import sys
from unittest.mock import MagicMock, patch

import httpx
from langchain_core.messages import AIMessage, ToolMessage

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
    to_remove = [key for key in list(sys.modules) if key.startswith("src.")]
    for key in to_remove:
        del sys.modules[key]


def _plain_model(*responses: AIMessage) -> MagicMock:
    model = MagicMock()
    model.profile = {"tool_calling": True}
    model.bind_tools.return_value = model
    model.bind.return_value = model
    model.invoke.side_effect = list(responses)
    return model


def test_jasper_text_strategy_produces_canonical_assistant_message():
    model = _plain_model(AIMessage(content="Hello! I can help with daily tasks."))

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = module.create_jasper_graph().invoke(
            {"messages": [{"role": "user", "content": "What can you do?"}]}
        )

    assert len(result["messages"]) == 2
    assert result["messages"][-1].content.startswith("Hello")
    assert result["jasper_response"] == result["messages"][-1].content
    assert result["visual_artifacts"] == []
    assert result["jasper_strategy"] == "text"


def test_jasper_provider_error_is_sanitized():
    model = MagicMock()
    model.profile = {"tool_calling": True}
    model.bind_tools.side_effect = httpx.ConnectError(
        "secret provider detail",
        request=httpx.Request("POST", "https://ollama.com/api/chat"),
    )

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = module.create_jasper_graph().invoke(
            {"messages": [{"role": "user", "content": "Test error handling"}]}
        )

    content = result["messages"][-1].content
    assert "selected model" in content
    assert "secret provider detail" not in content
    assert result["jasper_diagnostic"]["code"] == "provider_unavailable"


def test_jasper_internal_error_is_not_misreported_as_provider_failure():
    model = MagicMock()
    model.profile = {"tool_calling": True}
    model.bind_tools.side_effect = RuntimeError("internal agent failure")

    _clear_src_modules()
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "text"}),
        patch("src.llm.ChatOllama", return_value=model),
    ):
        module = importlib.import_module("src.jasper_agent")
        result = module.create_jasper_graph().invoke(
            {"messages": [{"role": "user", "content": "Test agent handling"}]}
        )

    assert "model responded" in result["messages"][-1].content
    assert result["jasper_diagnostic"]["code"] == "structured_output_invalid"


def test_jasper_recovers_when_tool_loop_returns_empty_final_content():
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
        result = module.create_jasper_graph().invoke(
            {"messages": [{"role": "user", "content": "Explain this"}]}
        )

    assert result["jasper_response"] == "Here is the recovered final answer."
    model.bind.assert_called_once_with(num_predict=4096)


def test_jasper_plain_agent_executes_tools_but_exposes_only_canonical_answer():
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
        result = module.create_jasper_graph().invoke(
            {"messages": [{"role": "user", "content": "What are my todos?"}]}
        )

    assert len(result["messages"]) == 2
    assert result["jasper_response"] == "Here is your todo list summary."


def test_text_strategy_does_not_bind_tools_for_incompatible_models():
    model = MagicMock()
    model.profile = {"tool_calling": False}
    captured = {}

    class TextAgent:
        def invoke(self, _state):
            return {"messages": [AIMessage(content="A safe text-only answer.")]}

    def build_agent(_model, response_format=None, *, tools=None):
        captured["response_format"] = response_format
        captured["tools"] = tools
        return TextAgent()

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with patch.object(module, "_build_agent", side_effect=build_agent):
        result = module._invoke_text(
            model, [{"role": "user", "content": "Answer in text"}]
        )

    assert result.voice_text == "A safe text-only answer."
    assert captured["tools"] == []


def test_two_pass_format_failure_preserves_the_plain_answer():
    model = _plain_model(AIMessage(content="The useful plain answer."))
    formatter = MagicMock()
    formatter.invoke.side_effect = ValueError("invalid structured response")
    model.with_structured_output.return_value = formatter

    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    with (
        patch.dict("os.environ", {"JASPER_STRUCTURED_STRATEGY": "auto"}),
        patch.object(module, "get_agent_llm", return_value=model),
    ):
        result = module.create_jasper_graph().invoke(
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


def test_two_pass_recovers_validated_tool_artifact_when_formatter_fails():
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
    model.with_structured_output.return_value.invoke.side_effect = ValueError(
        "invalid structured response"
    )

    with patch.object(module, "_invoke_plain", return_value=(evidence, "")):
        result = module._invoke_two_pass(model, [{"role": "user", "content": "Draw"}])

    assert result.voice_text == 'I created the "Request flow" concept map.'
    assert [item.artifact_id for item in result.artifacts] == ["request-flow"]
    assert result.layout_suggestion.mode == "split"
    assert result.diagnostic.code == "structured_output_invalid"


def test_two_pass_uses_tool_artifacts_instead_of_formatter_inventions():
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
    model.with_structured_output.return_value.invoke.return_value = JasperResponse(
        voice_text="Here is the request flow.",
        artifacts=[invented],
    )

    with patch.object(module, "_invoke_plain", return_value=(evidence, "")):
        result = module._invoke_two_pass(model, [{"role": "user", "content": "Draw"}])

    assert [item.artifact_id for item in result.artifacts] == ["request-flow"]


def test_combined_strategy_drops_artifacts_not_returned_by_visual_tool():
    module = importlib.import_module("src.jasper_agent")
    invented = _concept_map("Invented map")
    agent = MagicMock()
    agent.invoke.return_value = {
        "messages": [AIMessage(content="An unsupported diagram.")],
        "structured_response": {
            "version": 2,
            "voice_text": "An unsupported diagram.",
            "artifacts": [invented.model_dump(mode="json")],
        },
    }

    with patch.object(module, "_build_agent", return_value=agent):
        result = module._invoke_combined(
            MagicMock(), [{"role": "user", "content": "Draw"}], "tool"
        )

    assert result.artifacts == []
    assert result.layout_suggestion is None


def test_combined_strategy_associates_artifact_with_canonical_message():
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
        patch.object(module, "_invoke_combined", return_value=structured),
    ):
        result = module.create_jasper_graph().invoke(
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


def test_jasper_delegates_web_access_to_research_without_direct_web_tools():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    research_agent = MagicMock()

    with patch.object(module, "create_research_agent", return_value=research_agent):
        tools = module._active_tools(MagicMock())

    assert [tool.name for tool in tools] == [
        "list_todos",
        "read_file",
        "draw_concept_map",
        "research",
    ]


def test_jasper_research_tool_returns_specialist_final_answer():
    _clear_src_modules()
    module = importlib.import_module("src.jasper_agent")
    research_agent = MagicMock()
    research_agent.invoke.return_value = {
        "messages": [AIMessage(content="SIFT findings with evidence web-123.")]
    }

    with patch.object(module, "create_research_agent", return_value=research_agent):
        research = module._research_tool(MagicMock())
        result = research.invoke({"query": "Research the SIFT method."})

    assert result == "SIFT findings with evidence web-123."
    research_agent.invoke.assert_called_once_with(
        {"messages": [{"role": "user", "content": "Research the SIFT method."}]}
    )


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


def test_second_visual_request_returns_the_new_tool_artifact():
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
    model.with_structured_output.return_value.invoke.return_value = JasperResponse(
        voice_text="Here is the SIFT map.",
        artifacts=[current],
    )
    history = [
        {"role": "user", "content": "Draw the scientific method."},
        {"role": "assistant", "content": previous.title},
        {"role": "user", "content": "Now add a SIFT visualization."},
    ]

    with patch.object(module, "_invoke_plain", return_value=(evidence, "Done")):
        result = module._invoke_two_pass(model, history)

    assert [artifact.artifact_id for artifact in result.artifacts] == ["sift-map"]
