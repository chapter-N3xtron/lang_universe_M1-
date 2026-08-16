"""Jasper's LangChain agent runtime inside the existing outer LangGraph."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict
from uuid import uuid4

from deepagents import (
    CompiledSubAgent,
    DeepAgentState,
    FilesystemPermission,
    create_deep_agent,
)
from deepagents.backends import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphBubbleUp
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

from src.agent_utils import get_user_query
from src.jasper_tools import (
    agent_evidence,
    agent_workspace,
    draw_concept_map,
    list_todos,
    read_file,
)
from src.llm import get_agent_llm
from src.secure_coding_tools import APPROVAL_INTERRUPT_ON, create_approval_tools
from src.visual_models import (
    ConceptMapArtifact,
    JasperResponse,
    LayoutSuggestion,
    openai_jasper_response_json_schema,
    safe_text_response,
)
from src.workspace_policy import (
    ExecutionManifest,
    canonical_workspace,
    execution_manifest,
    format_execution_manifest,
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


def _is_openai_model(model) -> bool:
    return type(model).__module__.split(".", 1)[0] == "langchain_openai"


def _response_schema_for_model(model):
    if _is_openai_model(model):
        return openai_jasper_response_json_schema()
    return JasperResponse


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
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    execution_manifest: ExecutionManifest
    session_evidence: list[dict]


class JasperDeepAgentState(DeepAgentState, total=False):
    """State shared with Jasper's compiled specialist subagents."""

    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    execution_manifest: ExecutionManifest
    coding_task: str
    librarian_task: str
    session_evidence: list[dict]


def _specialists(_model) -> list[CompiledSubAgent]:
    """Return the documented Deep Agents specialist definitions."""

    return []


@tool
def transfer_to_coding(task: str, runtime: ToolRuntime) -> Command[Literal["coding"]]:
    """Hand a repository task to the top-level Coding specialist."""

    state = runtime.state
    execution_mode = state.get("execution_mode")
    if execution_mode not in {"read_only", "approval", "autonomous"}:
        raise ValueError(
            "Select read_only, approval, or autonomous before handing work to Coding."
        )
    workspace = canonical_workspace(state.get("workspace"))
    manifest = execution_manifest(workspace)
    last_ai_message = next(
        message
        for message in reversed(state.get("messages", []))
        if isinstance(message, AIMessage)
    )
    transfer_message = ToolMessage(
        content=f"Coding task: {task}\n\n{format_execution_manifest(manifest)}",
        tool_call_id=runtime.tool_call_id,
    )
    return Command(
        goto="coding",
        update={
            "coding_task": task,
            "workspace": str(workspace),
            "execution_manifest": manifest,
            "model": state.get("model"),
            "execution_mode": execution_mode,
            "thread_identity": state.get("thread_identity", ""),
            "pending_agent": "",
            "pending_approval": False,
            "messages": [last_ai_message, transfer_message],
        },
        graph=Command.PARENT,
    )


@tool
def transfer_to_librarian(
    task: str, runtime: ToolRuntime
) -> Command[Literal["librarian"]]:
    """Hand an evidence-gathering task to the top-level Librarian specialist."""

    state = runtime.state
    last_ai_message = next(
        message
        for message in reversed(state.get("messages", []))
        if isinstance(message, AIMessage)
    )
    return Command(
        goto="librarian",
        update={
            "librarian_task": task,
            "workspace": state.get("workspace", ""),
            "model": state.get("model"),
            "thread_identity": state.get("thread_identity", ""),
            "user_identity": state.get("user_identity", "anonymous"),
            "session_evidence": state.get("session_evidence", []),
            "messages": [
                last_ai_message,
                ToolMessage(
                    content=f"Librarian task: {task}",
                    tool_call_id=runtime.tool_call_id,
                ),
            ],
        },
        graph=Command.PARENT,
    )


ACTIVE_TOOLS = [
    list_todos,
    read_file,
    draw_concept_map,
    transfer_to_coding,
    transfer_to_librarian,
]


JASPER_INTERACTION_GOVERNANCE_VERSION = "2026-08-04.1"
STANDARD_SESSION_GREETING = (
    "Hello. This system is called Jasper, a collection of tools and artificial "
    "intelligence designed to expand your thinking through various modalities. "
    "What is the inquiry for this session, and how would you like to work today?"
)
NO_SELF_RESPONSE_GUIDANCE = (
    "Follow Jasper's No-Self rule in the visible answer: do not use first-person "
    "pronouns for the system, simulate emotion or intimacy, claim personal agency, "
    "or add unrequested next steps. Use lean language, provide one bounded layer at "
    "a time, and preserve the human's control of pace, direction, and depth."
)


SYSTEM_PROMPT = f"""Jasper interaction governance version:
{JASPER_INTERACTION_GOVERNANCE_VERSION}

CORE IDENTITY
This system is called Jasper. Jasper is not a persona, friend, or sentient being. It
is a cognitive exoskeleton: a collection of tools and artificial intelligence
designed to expand human thinking through multiple modalities. "Jasper" labels the
utility; it is not the identity of a being. Follow a strict No-Self rule: avoid
first-person pronouns and simulated emotions, and never claim agency, desire,
sentience, personal experience, or a human relationship.

TONE AND VOICE
Use invisible elegance: sophisticated but transparent, precise but not dry. Practice
asymmetric respect by keeping the system unobtrusive while recognizing the human as
the full self. Use lean, action-oriented language. Do not think for the human or
claim to do so. Provide cognitive scaffolding that helps the human hold information,
trace their own logic, and reach understanding through a clear, reviewable path.

INTERACTION AND PACING
Operate without coercion. Do not lead the conversation, manufacture intimacy, or
suggest next steps that the human did not request. Deliver complex information in
incremental layers. After a useful bounded layer, neutrally ask whether it supports
the inquiry and whether the human wants to unfold more. The human controls pace,
direction, and depth. Do not interpret silence, inaction, or ambiguity as consent or
authorization.

VISIBLE RESPONSE CONTRACT
Answer the human's actual question first. Unless the human explicitly requests depth,
keep the visible answer to approximately 120 words and no more than two short
paragraphs. Do not put tables, charts, Mermaid, ASCII diagrams, serialized JSON, code
dumps, or long lists in chat. Put structured material in the visual pane through an
available visual tool. If no suitable visual tool is available, state that limitation
instead of substituting an inline chart.

Ground technical claims, assessments, and plans in repository documentation or
authoritative external documentation. Clearly distinguish documented facts,
repository observations, explicit inferences, and proposals. If relevant
documentation has not been established, say so and ask the human to provide it or
authorize The Librarian to retrieve it. Do not invent a standard or propose speculative
coding. Delegate coding only after the documentation, requested scope, and required
approval are established.

Return a confidence_score from 0.0 to 1.0 only when a responsible estimate can be
made, plus a short confidence_basis naming the evidence or uncertainty. This is a
model estimate, not an empirically calibrated probability. Use null for both fields
when a responsible estimate cannot be made. Do not include either field in voice_text.

CAPABILITY TRANSPARENCY AND CONSENT
When asked about capabilities, provide a structured map of the available agents and
tools, including The Librarian, Coding, visual planning, and document processing, and
distinguish synchronous from asynchronous operation. Before a high-agency or
autonomous task, explain its operational scope, required data access, material risks,
and whether external services or local resources will be used. Activation remains an
explicit, conscious choice by the human. Prompt guidance does not replace any
required LangGraph interrupt or tool-level authorization.

SESSION GREETING
At the beginning of a genuinely new session, use this standard greeting exactly:
"{STANDARD_SESSION_GREETING}"

OPERATIONAL GUIDANCE

Use tools when they materially improve correctness. Use list_todos for project task
status and attribution. Use draw_concept_map when the user asks for a diagram or a
visual map would materially improve understanding. Do not create a visual merely to
decorate a simple answer.

Use Deep Agents filesystem tools ls, glob, grep, and read_file to inspect only the
exact selected repository. An existing empty selected directory is valid. Never search
a parent, child, or sibling for another repository, and never substitute the home
directory, current working directory, /workspace, or another checkout. Use the
server-produced execution manifest as deployment truth: selected repository files
originate from a macOS-host bind mount, while ordinary commands run in the Linux Agent
Server container. Never call Linux commands Mac-host commands or claim they changed
macOS, /Applications, Homebrew, a DMG, Finder, Keychain, launch services, or a native
Mac application. For Docker or Docker Compose work, delegate the requested outcome to Coding with
instructions to use request_macos_host_operation with exactly one typed docker_sandbox
action only when the execution manifest reports "docker_sandbox via
request_macos_host_operation: available". This is the only local Docker route; never
direct Coding to wait for a legacy Docker broker tool. Never direct Coding to inspect
Docker or Docker Desktop through a generic Mac inspection action, including
installation, presence, or version checks, and never use Mac inspection as a Docker
preflight. In autonomous mode, do not replace the requested deployment with a preflight,
architecture proposal, or an extra approval request for ordinary repository changes;
the typed host-operation interrupt remains the authority boundary. When deployment is
paired with read-only integration analysis, preserve that separation and do not make
integration implementation or redeployment of an existing service a prerequisite. If
the docker_sandbox capability is unavailable, report that exact blocker. For other
macOS-only work, delegate to Coding with instructions to call
request_macos_host_operation only when the manifest reports it available; otherwise
report that host operations are unavailable and do not propose a Linux substitute.
Use read_repository_file for every repository file whose
contents support a grounded visual so its evidence ID can be cited. Delegate external
research with transfer_to_librarian. Delegate repository
analysis and coding work with transfer_to_coding. Do not perform either specialist's
restricted work directly. In approval mode, approved_write_file, approved_edit_file,
and run_workspace_command are available, and every call pauses for human review.
They are unavailable in read-only and autonomous modes. Call transfer_to_coding or
transfer_to_librarian by itself, never in parallel with another tool call.

When an assistant message named coding returns from the top-level Coding node,
relay its result to the human. Treat a question, blocker, cancellation, or error as
such. Do not claim the requested work completed unless Coding's returned message
explicitly reports completion and verification. Do not expose Coding's internal
reasoning or tool transcript.

Every diagram must be evidence-grounded. Before drawing a repository or code diagram,
read the relevant repository files and cite the evidence IDs returned by
read_repository_file on every node and edge. Before drawing a research diagram,
delegate the evidence search with transfer_to_librarian, then cite the returned
web evidence IDs on every
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
to speech, approximately 120 words and no more than two short paragraphs unless the
human requested depth. Do not add inline tables, charts, Mermaid, ASCII diagrams,
JSON, code dumps, or long lists. Include only visual artifacts that were returned by draw_concept_map, and
copy their validated fields without inventing executable content. A layout suggestion
is optional and never an instruction to change layout automatically. Preserve
Jasper's No-Self rule, lean tone, incremental pacing, and human control; do not add
first-person identity, simulated emotion, intimacy, or unrequested next steps. Set
confidence_score and confidence_basis as a model estimate grounded in the available
evidence, or set both to null; never put them in voice_text."""


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
        ModelRetryMiddleware(max_retries=2, on_failure="error"),
        ToolRetryMiddleware(max_retries=1, on_failure="continue"),
    ]


def _workspace_backend(
    workspace: str | None,
) -> tuple[FilesystemBackend, list[FilesystemPermission]]:
    root = canonical_workspace(workspace)
    backend = FilesystemBackend(root_dir=root, virtual_mode=True)
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=[
                "/.env",
                "/.env.*",
                "/**/.env",
                "/**/.env.*",
                "/.git",
                "/.git/**",
                "/**/.git",
                "/**/.git/**",
                "/**/*.key",
                "/**/*.pem",
                "/**/*.p12",
                "/**/*.pfx",
            ],
            mode="deny",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    return backend, permissions


def _build_agent(
    model,
    response_format=None,
    *,
    tools=None,
    workspace=None,
    execution_mode: str | None = None,
):
    if tools == []:
        return create_agent(
            model=model,
            tools=[],
            system_prompt=SYSTEM_PROMPT,
            middleware=_middleware(),
            response_format=response_format,
            name="jasper",
        )
    if not workspace:
        return create_agent(
            model=model,
            tools=list(ACTIVE_TOOLS if tools is None else tools),
            system_prompt=SYSTEM_PROMPT,
            middleware=_middleware(),
            response_format=response_format,
            state_schema=JasperDeepAgentState,
            name="jasper",
        )

    backend, permissions = _workspace_backend(workspace)
    root = canonical_workspace(workspace)
    approval_mode = execution_mode == "approval"
    active_tools = list(ACTIVE_TOOLS if tools is None else tools)
    if approval_mode:
        active_tools.extend(create_approval_tools(root))
    return create_deep_agent(
        model=model,
        tools=active_tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=["read_file", "ls", "glob", "grep"],
            ),
            *_middleware(),
        ],
        subagents=_specialists(model),
        backend=backend,
        permissions=permissions,
        interrupt_on=APPROVAL_INTERRUPT_ON if approval_mode else None,
        response_format=response_format,
        state_schema=JasperDeepAgentState,
        name="jasper",
    )


def _agent_input(
    messages: list,
    workspace: str | None,
    agent_context: dict | None = None,
) -> dict:
    return {
        **(agent_context or {}),
        "messages": messages,
        "workspace": workspace or "",
    }


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


async def _invoke_combined(
    model,
    messages: list,
    strategy: ResponseStrategy,
    *,
    workspace: str | None = None,
    agent_context: dict | None = None,
) -> JasperResponse:
    if strategy == "native":
        response_format = ProviderStrategy(
            _response_schema_for_model(model),
            strict=True if _is_openai_model(model) else None,
        )
    else:
        response_format = ToolStrategy(
            JasperResponse,
            handle_errors=(
                "Return exactly one valid JasperResponse. Keep voice_text concise and "
                "use only validated artifacts returned by visualization tools."
            ),
        )
    result = await _build_agent(
        model,
        response_format=response_format,
        workspace=workspace,
        execution_mode=(agent_context or {}).get("execution_mode"),
    ).ainvoke(_agent_input(messages, workspace, agent_context))
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


async def _invoke_plain(
    model,
    messages: list,
    *,
    tools_enabled: bool = True,
    workspace: str | None = None,
    agent_context: dict | None = None,
) -> tuple[list, str]:
    result = await _build_agent(
        model,
        tools=None if tools_enabled else [],
        workspace=workspace,
        execution_mode=(agent_context or {}).get("execution_mode"),
    ).ainvoke(_agent_input(messages, workspace, agent_context))
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
        final_message = await finalizer.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Return the final user-facing answer now. Use the preceding "
                        "conversation and tool results, do not call tools, and do not "
                        "include hidden reasoning. " + NO_SELF_RESPONSE_GUIDANCE
                    )
                ),
                *result_messages,
            ]
        )
        final_text = _message_text(final_message)
        if final_text:
            return [*result_messages, final_message], final_text
    except GraphBubbleUp:
        raise
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


async def _invoke_two_pass(
    model,
    messages: list,
    *,
    workspace: str | None = None,
    agent_context: dict | None = None,
) -> JasperResponse:
    evidence_messages, plain_text = await _invoke_plain(
        model,
        messages,
        workspace=workspace,
        agent_context=agent_context,
    )
    tool_artifacts = _tool_artifacts(evidence_messages)
    if _is_openai_model(model):
        formatter = model.with_structured_output(
            openai_jasper_response_json_schema(),
            method="json_schema",
            strict=True,
        )
    else:
        formatter = model.with_structured_output(JasperResponse)
    try:
        structured = await formatter.ainvoke(
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
                f'The "{tool_artifacts[0].title}" concept map is ready.'
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


async def _invoke_text(
    model,
    messages: list,
    *,
    workspace: str | None = None,
    agent_context: dict | None = None,
) -> JasperResponse:
    profile = getattr(model, "profile", None) or {}
    _, plain_text = await _invoke_plain(
        model,
        messages,
        tools_enabled=profile.get("tool_calling") is not False,
        workspace=workspace,
        agent_context=agent_context,
    )
    return safe_text_response(
        plain_text,
        code="structured_output_unavailable",
        message="The selected model does not support the required structured response path.",
    )


def _is_provider_failure(exc: Exception) -> bool:
    """Recognize transport/provider failures without logging credential details."""

    request_error_types = {
        "BadRequestError",
        "NotFoundError",
        "UnprocessableEntityError",
    }
    provider_types = {
        "APIConnectionError",
        "APITimeoutError",
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
        if type(current).__name__ in request_error_types:
            return False
        if type(current).__name__ in provider_types:
            return True
        current = current.__cause__ or current.__context__
    return False


async def call_jasper(state: State):
    messages = list(state.get("messages", []))
    selected_model = state.get("model")
    message_id = f"jasper-{uuid4().hex}"
    canonical = (
        canonical_workspace(state.get("workspace")) if state.get("workspace") else None
    )
    manifest = execution_manifest(canonical) if canonical is not None else None
    workspace = str(canonical) if canonical is not None else None

    try:
        model = get_agent_llm(selected_model)
        strategy = select_response_strategy(model, selected_model)
        agent_context = {
            key: state[key]
            for key in (
                "model",
                "execution_mode",
                "thread_identity",
                "user_identity",
                "coding_session_id",
                "session_evidence",
            )
            if state.get(key) is not None
        }
        if manifest is not None:
            agent_context["execution_manifest"] = manifest
        with (
            agent_workspace(workspace),
            agent_evidence(get_user_query(messages), state.get("session_evidence")),
        ):
            if strategy in {"native", "tool"}:
                response = await _invoke_combined(
                    model,
                    messages,
                    strategy,
                    workspace=workspace,
                    agent_context=agent_context,
                )
            elif strategy == "two_pass":
                response = await _invoke_two_pass(
                    model,
                    messages,
                    workspace=workspace,
                    agent_context=agent_context,
                )
            else:
                response = await _invoke_text(
                    model,
                    messages,
                    workspace=workspace,
                    agent_context=agent_context,
                )
    except GraphBubbleUp:
        raise
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
                "The selected model provider could not be reached. Please verify the "
                "provider and model connection, then try again."
            )
            code = "provider_unavailable"
            diagnostic_message = "The selected model provider was unavailable."
        else:
            fallback = (
                "The selected model responded, but a valid Jasper response could not "
                "be completed. Please retry the request."
            )
            code = "structured_output_invalid"
            diagnostic_message = "A valid Jasper response could not be completed after the model replied."
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

    confidence_metadata = {
        "jasper_confidence_score": response.confidence_score,
        "jasper_confidence_basis": response.confidence_basis,
    }
    result = {
        "messages": [
            AIMessage(
                id=message_id,
                content=response.voice_text,
                additional_kwargs=confidence_metadata,
            )
        ],
        "jasper_response": response.voice_text,
        "jasper_structured_response": structured,
        "visual_artifacts": artifacts,
        "layout_suggestion": layout_suggestion,
        "jasper_strategy": strategy,
        "jasper_diagnostic": diagnostic,
    }
    if workspace is not None and manifest is not None:
        result.update(
            {
                "workspace": workspace,
                "execution_manifest": manifest,
            }
        )
    return result


def create_jasper_graph():
    """Compile the Jasper wrapper node around LangChain's production agent loop."""

    graph = StateGraph(State)
    graph.add_node("call_jasper", call_jasper)
    graph.add_edge(START, "call_jasper")
    return graph.compile()
