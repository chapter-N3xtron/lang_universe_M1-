"""Jasper's LangChain agent runtime inside the existing outer LangGraph."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages

from src.agent_utils import get_user_query
from src.jasper_tools import (
    agent_evidence,
    agent_workspace,
    draw_concept_map,
    list_todos,
    read_file,
)
from src.llm import get_agent_llm
from src.research_agent import create_research_agent
from src.visual_models import (
    ConceptMapArtifact,
    JasperResponse,
    LayoutSuggestion,
    safe_text_response,
)

logger = logging.getLogger(__name__)

ResponseStrategy = Literal["native", "tool", "two_pass", "text"]
VALID_STRATEGIES = frozenset({"auto", "native", "tool", "two_pass", "text"})


@dataclass(frozen=True)
class VerifiedModelCapability:
    strategy: ResponseStrategy
    verified_at: str
    evidence: str


# Entries are added only after the repository's live combined-capability test
# passes for that exact provider/model ID. Empty is safer than guessed support.
VERIFIED_MODEL_CAPABILITIES: dict[str, VerifiedModelCapability] = {}


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    jasper_response: str
    jasper_structured_response: dict
    visual_artifacts: list[dict]
    layout_suggestion: dict | None
    jasper_strategy: ResponseStrategy
    jasper_diagnostic: dict | None
    todos: list[dict]
    model: str
    workspace: str


ACTIVE_TOOLS = [list_todos, read_file, draw_concept_map]


def _research_tool(model):
    research_agent = create_research_agent(model)

    @tool(
        "research",
        description=(
            "Delegate web research and URL reading to the Research specialist. "
            "Returns concise findings with evidence IDs for grounded answers and visuals."
        ),
    )
    def research(query: str) -> str:
        result = research_agent.invoke(
            {"messages": [{"role": "user", "content": query}]}
        )
        return _message_text(result["messages"][-1])

    return research


def _active_tools(model):
    """Return Jasper's direct tools plus the documented Research subagent tool."""

    return [*ACTIVE_TOOLS, _research_tool(model)]


SYSTEM_PROMPT = """You are Jasper, a dependable daily-driver assistant.

Use tools when they materially improve correctness. Use list_todos for project task
status and attribution. Use draw_concept_map when the user asks for a diagram or a
visual map would materially improve understanding. Do not create a visual merely to
decorate a simple answer.

Every diagram must be evidence-grounded. Before drawing a repository or code diagram,
read the relevant repository files and cite the evidence IDs returned by read_file on
every node and edge. Before drawing a research diagram, delegate the evidence search
to Research with the research tool, then cite the returned web evidence IDs on every
node and edge. Use grounding_kind="repo" for repository diagrams and "web" for researched
claims. The user-input evidence may support only claims explicitly stated by the user;
cite it with the exact evidence ID "user-input". It is not evidence for repository
structure or external facts. If adequate evidence
cannot be obtained, explain the limitation and do not draw the diagram.

Label every node and edge with an honest claim_status: "observed" for repository
facts, "researched" for web-supported facts, "user_defined" for a process or
framework supplied by the user, "proposed" for a not-yet-built design, and
"inferred" only for an explicit inference from cited evidence. Never label a
proposed or user-defined architecture as observed implementation.

Give every node a concise, voice-friendly narration grounded in the same cited
evidence, and provide narration_order in the order Jasper should explain and
highlight the nodes. Include every node exactly once in that order.

When draw_concept_map returns an artifact, preserve that validated artifact in the
final structured response. The voice_text must be natural spoken language: no tables,
serialized JSON, code dumps, or descriptions of UI controls. A layout suggestion is
advisory only; the human always controls the workspace layout.

Never request, reveal, reproduce, or summarize credentials, environment files,
private keys, authentication headers, or secrets. Be concise, accurate, and explicit
when a tool or provider is unavailable."""

FORMATTER_PROMPT = """Convert the completed Jasper agent result into the required
JasperResponse schema. Preserve the answer's facts. Keep voice_text natural for text
to speech. Include only visual artifacts that were returned by draw_concept_map, and
copy their validated fields without inventing executable content. A layout suggestion
is optional and never an instruction to change layout automatically."""


def select_response_strategy(model, requested: str | None = None) -> ResponseStrategy:
    """Select a deterministic structured-response strategy.

    `JASPER_STRUCTURED_STRATEGY` is an operator-controlled, testable override. In
    auto mode, combined tool/structured output is used only when a model profile
    explicitly reports the repo-specific `structured_output_with_tools` capability.
    Unknown profiles take the conservative two-pass path.
    """

    configured = os.getenv("JASPER_STRUCTURED_STRATEGY", "auto").strip().lower()
    if configured not in VALID_STRATEGIES:
        configured = "auto"
    if configured != "auto":
        return configured  # type: ignore[return-value]

    if requested and requested in VERIFIED_MODEL_CAPABILITIES:
        return VERIFIED_MODEL_CAPABILITIES[requested].strategy

    profile = getattr(model, "profile", None) or {}
    if profile.get("tool_calling") is False:
        return "text"
    if profile.get("structured_output_with_tools") is True:
        return "native" if profile.get("structured_output") is True else "tool"

    # Do not infer simultaneous capability from provider or model names.
    return "two_pass"


def _middleware():
    return [
        ModelCallLimitMiddleware(run_limit=8, exit_behavior="error"),
        ModelRetryMiddleware(max_retries=2, on_failure="error"),
        ToolRetryMiddleware(max_retries=1),
    ]


def _build_agent(model, response_format=None, *, tools=None):
    return create_agent(
        model=model,
        tools=_active_tools(model) if tools is None else tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=_middleware(),
        response_format=response_format,
        name="jasper",
    )


def _message_text(message: BaseMessage | dict | None) -> str:
    if message is None:
        return ""
    content = (
        message.get("content", "") if isinstance(message, dict) else message.content
    )
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    return ""


def _last_assistant_text(messages: list) -> str:
    for message in reversed(messages):
        msg_type = message.get("role") if isinstance(message, dict) else message.type
        if msg_type in {"assistant", "ai"}:
            text = _message_text(message)
            if text:
                return text
    return ""


def _invoke_combined(
    model, messages: list, strategy: ResponseStrategy
) -> JasperResponse:
    if strategy == "native":
        response_format = ProviderStrategy(JasperResponse)
    else:
        response_format = ToolStrategy(
            JasperResponse,
            handle_errors=(
                "Return exactly one valid JasperResponse. Keep voice_text concise and "
                "use only validated artifacts returned by visualization tools."
            ),
        )
    result = _build_agent(model, response_format=response_format).invoke(
        {"messages": messages}
    )
    response = JasperResponse.model_validate(result["structured_response"])
    tool_artifacts = _tool_artifacts(result.get("messages", []))
    return response.model_copy(
        update={
            "artifacts": tool_artifacts,
            "layout_suggestion": (
                response.layout_suggestion if tool_artifacts else None
            ),
        }
    )


def _invoke_plain(
    model, messages: list, *, tools_enabled: bool = True
) -> tuple[list, str]:
    result = _build_agent(model, tools=None if tools_enabled else []).invoke(
        {"messages": messages}
    )
    result_messages = result.get("messages", [])
    plain_text = _last_assistant_text(result_messages)
    if plain_text:
        return result_messages, plain_text

    # Some reasoning models can finish a tool loop with an empty content field,
    # especially when their reasoning consumes the response budget. Ask the
    # unbound model for one final user-facing answer before falling back.
    try:
        finalizer = model.bind(
            num_predict=int(os.getenv("JASPER_FINAL_NUM_PREDICT", "4096"))
        )
        final_message = finalizer.invoke(
            [
                SystemMessage(
                    content=(
                        "Return the final user-facing answer now. Use the preceding "
                        "conversation and tool results, do not call tools, and do not "
                        "include hidden reasoning."
                    )
                ),
                *result_messages,
            ]
        )
        final_text = _message_text(final_message)
        if final_text:
            return [*result_messages, final_message], final_text
    except Exception as exc:
        logger.warning("Jasper final-answer recovery failed: %s", type(exc).__name__)

    return (
        result_messages,
        "The selected model completed its processing but returned no final text. "
        "Please retry the request.",
    )


def _tool_artifacts(messages: list) -> list[ConceptMapArtifact]:
    """Recover only artifacts that passed through the validated visual tool."""

    artifacts = []
    seen = set()
    for message in messages:
        name = (
            message.get("name")
            if isinstance(message, dict)
            else getattr(message, "name", None)
        )
        if name != "draw_concept_map":
            continue
        content = (
            message.get("content") if isinstance(message, dict) else message.content
        )
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        try:
            artifact = ConceptMapArtifact.model_validate(content)
        except Exception:
            continue
        if artifact.artifact_id not in seen:
            seen.add(artifact.artifact_id)
            artifacts.append(artifact)
    return artifacts[:4]


def _invoke_two_pass(model, messages: list) -> JasperResponse:
    evidence_messages, plain_text = _invoke_plain(model, messages)
    tool_artifacts = _tool_artifacts(evidence_messages)
    formatter = model.with_structured_output(JasperResponse)
    try:
        structured = formatter.invoke(
            [SystemMessage(content=FORMATTER_PROMPT), *evidence_messages]
        )
        validated = JasperResponse.model_validate(structured)
        return validated.model_copy(
            update={
                "artifacts": tool_artifacts,
                "layout_suggestion": (
                    validated.layout_suggestion if tool_artifacts else None
                ),
            }
        )
    except Exception:
        logger.warning("Jasper structured formatting failed; using safe text response")
        recovered = safe_text_response(
            plain_text
            or (
                f'I created the "{tool_artifacts[0].title}" concept map.'
                if tool_artifacts
                else ""
            ),
            code="structured_output_invalid",
            message=(
                "The selected model could not format the complete structured "
                "response; validated tool results were recovered when available."
            ),
        )
        if not tool_artifacts:
            return recovered
        return recovered.model_copy(
            update={
                "artifacts": tool_artifacts,
                "layout_suggestion": LayoutSuggestion(
                    mode="split",
                    reason="View the concept map beside Jasper's explanation.",
                ),
            }
        )


def _invoke_text(model, messages: list) -> JasperResponse:
    profile = getattr(model, "profile", None) or {}
    _, plain_text = _invoke_plain(
        model,
        messages,
        tools_enabled=profile.get("tool_calling") is not False,
    )
    return safe_text_response(
        plain_text,
        code="structured_output_unavailable",
        message="The selected model does not support the required structured response path.",
    )


def _is_provider_failure(exc: Exception) -> bool:
    """Recognize transport/provider failures without logging credential details."""

    provider_types = {
        "ConnectError",
        "ConnectionError",
        "ConnectTimeout",
        "HTTPStatusError",
        "ReadTimeout",
        "RemoteProtocolError",
        "ResponseError",
        "Timeout",
        "TimeoutException",
    }
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if type(current).__name__ in provider_types:
            return True
        current = current.__cause__ or current.__context__
    return False


def call_jasper(state: State):
    messages = list(state.get("messages", []))
    selected_model = state.get("model")
    message_id = f"jasper-{uuid4().hex}"

    try:
        model = get_agent_llm(selected_model)
        strategy = select_response_strategy(model, selected_model)
        with (
            agent_workspace(state.get("workspace")),
            agent_evidence(get_user_query(messages)),
        ):
            if strategy in {"native", "tool"}:
                response = _invoke_combined(model, messages, strategy)
            elif strategy == "two_pass":
                response = _invoke_two_pass(model, messages)
            else:
                response = _invoke_text(model, messages)
    except Exception as exc:
        provider_failure = _is_provider_failure(exc)
        logger.warning(
            "Jasper execution failed: category=%s type=%s",
            "provider" if provider_failure else "agent",
            type(exc).__name__,
        )
        user_text = get_user_query(messages)
        if provider_failure:
            fallback = (
                "I could not reach the selected model. Please verify the provider and "
                "model connection, then try again."
            )
            code = "provider_unavailable"
            diagnostic_message = "The selected model provider was unavailable."
        else:
            fallback = (
                "The selected model responded, but Jasper could not complete the "
                "agent response. Please retry the request."
            )
            code = "structured_output_invalid"
            diagnostic_message = (
                "Jasper could not complete a valid response after the model replied."
            )
        if user_text:
            fallback += " Your request was preserved."
        response = safe_text_response(
            fallback,
            code=code,
            message=diagnostic_message,
        )
        strategy = "text"

    artifacts = []
    for artifact in response.artifacts:
        if artifact.source_message_id is None:
            artifact = artifact.model_copy(update={"source_message_id": message_id})
        artifacts.append(artifact.model_dump(mode="json"))

    diagnostic = (
        response.diagnostic.model_dump(mode="json") if response.diagnostic else None
    )
    layout_suggestion = (
        response.layout_suggestion.model_dump(mode="json")
        if response.layout_suggestion
        else None
    )
    structured = response.model_dump(mode="json")
    structured["artifacts"] = artifacts

    return {
        "messages": [AIMessage(id=message_id, content=response.voice_text)],
        "jasper_response": response.voice_text,
        "jasper_structured_response": structured,
        "visual_artifacts": artifacts,
        "layout_suggestion": layout_suggestion,
        "jasper_strategy": strategy,
        "jasper_diagnostic": diagnostic,
    }


def create_jasper_graph():
    """Compile the Jasper wrapper node around LangChain's production agent loop."""

    graph = StateGraph(State)
    graph.add_node("call_jasper", call_jasper)
    graph.add_edge(START, "call_jasper")
    return graph.compile()
