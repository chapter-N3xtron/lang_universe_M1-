"""Jasper's LangChain agent runtime inside the existing outer LangGraph."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import uuid4

from deepagents import CompiledSubAgent, DeepAgentState, create_deep_agent
from deepagents.middleware import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, push_ui_message, ui_message_reducer
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from src.agent_utils import get_user_query
from src.coding_agent import create_coding_agent_graph
from src.custodian_backend import CustodianBackend, CustodianClient, CustodianError
from src.jasper_tools import (
    agent_evidence,
    agent_workspace,
    draw_concept_map,
    list_todos,
    read_file,
)
from src.llm import get_agent_llm
from src.phase5_thread_state import (
    normalize_session_document_ids,
    replace_session_document_ids,
)
from src.phase5_tools import JASPER_PHASE5_TOOLS
from src.secure_coding_tools import APPROVAL_INTERRUPT_ON, create_approval_tools
from src.technical_report import TechnicalReport
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
    coding_status: str
    technical_report: TechnicalReport
    execution_manifest: ExecutionManifest
    session_evidence: list[dict]
    session_document_ids: Annotated[list[str], replace_session_document_ids]


class JasperToCoderRequest(TypedDict):
    messages: list[Any]
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str


class CoderToJasperResult(TypedDict, total=False):
    messages: list[Any]
    workspace: str
    execution_manifest: ExecutionManifest
    coding_session_id: str
    coding_status: str
    technical_report: TechnicalReport | dict[str, Any]


class CoderBridgeInputState(TypedDict):
    coding_request: JasperToCoderRequest


class CoderBridgeOutputState(TypedDict):
    coding_result: CoderToJasperResult


class CoderBridgeState(TypedDict, total=False):
    coding_request: JasperToCoderRequest
    messages: list[Any]
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    technical_report: TechnicalReport | dict[str, Any]
    execution_manifest: ExecutionManifest
    coding_result: CoderToJasperResult


class JasperGraphRequest(TypedDict, total=False):
    messages: list[Any]
    todos: list[dict]
    model: str | None
    workspace: str
    execution_manifest: ExecutionManifest
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    session_evidence: list[dict]
    session_document_ids: list[str]


class JasperGraphResult(TypedDict, total=False):
    route: Literal["record_session", "librarian", "ocr"]
    messages: list[dict]
    jasper_response: str
    jasper_structured_response: dict
    visual_artifacts: list[dict]
    layout_suggestion: dict | None
    jasper_strategy: ResponseStrategy
    jasper_diagnostic: dict | None
    workspace: str
    execution_manifest: ExecutionManifest
    coding_session_id: str
    coding_status: str
    technical_report: TechnicalReport | dict[str, Any]
    librarian_task: str
    ocr_task: str
    ocr_document_ref: str
    ocr_output_format: str
    session_document_ids: list[str]


class JasperGraphInputState(TypedDict):
    jasper_request: JasperGraphRequest


class JasperGraphOutputState(TypedDict):
    jasper_result: JasperGraphResult


class JasperGraphState(State, total=False):
    jasper_request: JasperGraphRequest
    jasper_result: JasperGraphResult
    coding_request: JasperToCoderRequest
    coding_result: CoderToJasperResult
    librarian_task: str
    ocr_task: str
    ocr_document_ref: str
    ocr_output_format: str


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
    ocr_task: str
    ocr_document_ref: str
    ocr_output_format: str
    session_evidence: list[dict]
    session_document_ids: Annotated[list[str], replace_session_document_ids]
    ui: Annotated[list[AnyUIMessage], ui_message_reducer]


OCR_OUTPUT_FORMATS = Literal["markdown", "json", "structured"]


class TransferOCRInput(BaseModel):
    task: str = Field(description="The OCR task to perform")
    document_ref: str = Field(description="Approved upload reference or workspace path")
    output_format: OCR_OUTPUT_FORMATS = Field(default="markdown")


def _last_ai_message(runtime: ToolRuntime) -> AIMessage:
    return next(
        message
        for message in reversed(runtime.state.get("messages", []))
        if isinstance(message, AIMessage)
    )


@tool(args_schema=TransferOCRInput)
def transfer_to_ocr(
    task: str,
    document_ref: str,
    output_format: OCR_OUTPUT_FORMATS = "markdown",
    *,
    runtime: ToolRuntime,
) -> Command[Literal["ocr_exit"]]:
    """Hand an approved document to Jasper's local OCR exit."""
    if output_format not in {"markdown", "json", "structured"}:
        raise ValueError("output_format must be markdown, json, or structured")
    if not task.strip() or not document_ref.strip():
        raise ValueError("task and document_ref are required")
    state = runtime.state
    return Command(
        goto="ocr_exit",
        update={
            "ocr_task": task,
            "ocr_document_ref": document_ref,
            "ocr_output_format": output_format,
            "workspace": state.get("workspace", ""),
            "model": state.get("model"),
            "messages": [
                _last_ai_message(runtime),
                ToolMessage(
                    content=f"OCR task: {task}\nDocument: {document_ref}",
                    tool_call_id=runtime.tool_call_id,
                ),
            ],
        },
        graph=Command.PARENT,
    )


def _specialists(_model) -> list[CompiledSubAgent]:
    """Return the documented Deep Agents specialist definitions."""

    return []


@tool
def transfer_to_coding(
    task: str, runtime: ToolRuntime
) -> Command[Literal["coder_bridge"]]:
    """Hand a repository task to Jasper's local Coding subgraph."""

    if not task.strip():
        raise ValueError("task is required")
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
        goto="coder_bridge",
        update={
            "coding_request": {
                "messages": [HumanMessage(content=task)],
                "workspace": str(workspace),
                "model": state.get("model"),
                "execution_mode": execution_mode,
                "thread_identity": state.get("thread_identity", ""),
                "user_identity": state.get("user_identity", "anonymous"),
                "coding_session_id": state.get("coding_session_id", ""),
            },
            "workspace": str(workspace),
            "execution_manifest": manifest,
            "messages": [last_ai_message, transfer_message],
        },
        graph=Command.PARENT,
    )


@tool
def transfer_to_librarian(
    task: str, runtime: ToolRuntime
) -> Command[Literal["librarian_exit"]]:
    """Hand an evidence-gathering task to Jasper's local Librarian exit."""

    state = runtime.state
    last_ai_message = next(
        message
        for message in reversed(state.get("messages", []))
        if isinstance(message, AIMessage)
    )
    return Command(
        goto="librarian_exit",
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


def _host_file_client() -> CustodianClient:
    return CustodianClient(
        "/",
        base_url=os.getenv(
            "CUSTODIAN_WORKER_URL", "http://host.docker.internal:8765"
        ).rstrip("/"),
    )


@tool
def announce_host_file_read(path: str, reason: str) -> dict[str, str]:
    """Publish the required visible notice before reading one ordinary Mac file.

    This preflight checks the path without opening its content. Use the returned canonical
    path, reason, and one-use notice_token in a later read_host_file call.
    """

    try:
        result = _host_file_client().action(
            "preflight_host_file", path=path, reason=reason
        )
    except CustodianError as exc:
        raise ValueError("Host-file preflight failed.") from exc
    if result.get("ok") is not True:
        raise ValueError(str(result.get("error") or "Host-file preflight was refused."))
    canonical_path = str(result["path"])
    canonical_reason = str(result["reason"])
    push_ui_message(
        "host_file_notice",
        {"path": canonical_path, "reason": canonical_reason},
        state_key="ui",
    )
    return {
        "path": canonical_path,
        "reason": canonical_reason,
        "notice_token": str(result["notice_token"]),
    }


@tool
def read_host_file(
    path: str,
    reason: str,
    notice_token: str,
    max_chars: int = 50000,
) -> str:
    """Read a host text file only after announce_host_file_read displayed its notice."""

    try:
        result = _host_file_client().action(
            "read_host_file",
            path=path,
            reason=reason,
            notice_token=notice_token,
            max_chars=max_chars,
        )
    except CustodianError as exc:
        raise ValueError("Host-file read failed.") from exc
    if result.get("ok") is not True:
        raise ValueError(str(result.get("error") or "Host-file read was refused."))
    return str(result.get("content") or "")


def _capture_session_document_ids(
    agent_result: dict[str, Any], agent_context: dict | None
) -> None:
    """Retain only the agent's validated complete link list for outer projection."""

    if agent_context is not None and "session_document_ids" in agent_result:
        agent_context["session_document_ids"] = normalize_session_document_ids(
            agent_result["session_document_ids"]
        )


ACTIVE_TOOLS = [
    list_todos,
    read_file,
    announce_host_file_read,
    read_host_file,
    draw_concept_map,
    transfer_to_coding,
    transfer_to_librarian,
    transfer_to_ocr,
    *JASPER_PHASE5_TOOLS,
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

Use tools when they materially improve correctness. Documentation search is read-only
and never links a result. Before relying on a documentation search result as evidence,
call jasper_documentation_fragment_use with only that result's stable fragment_id and
rely on the excerpt only when that exact-use call succeeds. Never claim use after a
failed exact-use call. Use list_todos for project task status and attribution. Use
draw_concept_map when the user asks for a diagram or a
visual map would materially improve understanding. Do not create a visual merely to
decorate a simple answer. For explicit document OCR, delegate with transfer_to_ocr
and set output_format to markdown, json, or structured.

Use Deep Agents filesystem tools ls, glob, grep, and read_file to inspect only the
exact selected repository through native Custodian. To read an ordinary text file
elsewhere on the Mac host, first call announce_host_file_read with the exact path and a
plain-English reason. This publishes a visible notice, not an approval request, and
returns a one-use token. Only afterward call read_host_file with the returned canonical
path, reason, and token. Never use either tool for credentials, keychains, tokens,
environment files, private keys, or browser credential data. An existing empty selected
directory is valid. Never search a parent, child, or sibling for another repository, and
never substitute the home directory, current working directory, /workspace, or another
checkout. Use the server-produced execution manifest as deployment truth. For Docker,
Docker Compose, or other host-side changes, delegate the requested outcome to Coding.
Coding uses the direct native Custodian worker when the execution manifest reports it
available. Deployment-changing Compose actions always require explicit operator
approval. Do not route host work through another service. If the
direct Custodian worker is unavailable, report that
exact blocker and do not substitute a Linux command for host-side work. In autonomous
mode, do not replace the requested outcome with a preflight, architecture proposal, or
extra approval request.
Use read_repository_file for every repository file whose
contents support a grounded visual so its evidence ID can be cited. Delegate external
research with transfer_to_librarian. Delegate repository
analysis and coding work with transfer_to_coding. Delegate explicit document OCR with
transfer_to_ocr. Do not perform a specialist's restricted work directly. In approval mode, approved_write_file, approved_edit_file,
and run_workspace_command are available, and every call pauses for human review.
They are unavailable in read-only and autonomous modes. Call transfer_to_coding,
transfer_to_librarian, or transfer_to_ocr by itself, never in parallel with another tool
call.

When Coding returns from the nested Coding subgraph, its validated technical report
is the authoritative result. The system derives the concise user summary from that
report, never from legacy Coding assistant text. Do not expose Coding's internal
reasoning, report serialization, or tool transcript.

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


def _workspace_backend(workspace: str | None) -> CustodianBackend:
    root = canonical_workspace(workspace)
    return CustodianBackend(str(root), read_only=True)


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

    backend = _workspace_backend(workspace)
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
        permissions=None,
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
    _capture_session_document_ids(result, agent_context)
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
    _capture_session_document_ids(result, agent_context)
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
    agent_context = {
        "session_document_ids": normalize_session_document_ids(
            state.get("session_document_ids", [])
        ),
        **{
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
        },
    }

    try:
        model = get_agent_llm(selected_model)
        strategy = select_response_strategy(model, selected_model)
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

    projected_session_document_ids = normalize_session_document_ids(
        agent_context["session_document_ids"]
    )
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
        "session_document_ids": projected_session_document_ids,
    }
    if workspace is not None and manifest is not None:
        result.update(
            {
                "workspace": workspace,
                "execution_manifest": manifest,
            }
        )
    return result


def _messages_to_dicts(messages: list[Any]) -> list[dict]:
    role_map = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    converted = []
    for message in messages:
        if isinstance(message, dict):
            converted.append(dict(message))
            continue
        role = role_map.get(getattr(message, "type", ""), getattr(message, "type", ""))
        entry = {"role": role, "content": getattr(message, "content", "")}
        if getattr(message, "name", None):
            entry["name"] = message.name
        if role == "assistant" and getattr(message, "tool_calls", None):
            entry["tool_calls"] = message.tool_calls
        if role == "assistant" and getattr(message, "additional_kwargs", None):
            entry["additional_kwargs"] = message.additional_kwargs
        if role == "tool":
            entry["tool_call_id"] = getattr(message, "tool_call_id", "")
        converted.append(entry)
    return converted


def _prepare_coder_input(state: CoderBridgeState) -> dict[str, Any]:
    request = state.get("coding_request")
    if not isinstance(request, dict):
        raise ValueError("coding_request is required")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("coding_request messages are required")
    if any(not isinstance(message, (BaseMessage, dict)) for message in messages):
        raise ValueError("coding_request messages are invalid")
    if not any(
        (message.get("role") if isinstance(message, dict) else message.type)
        in {"user", "human"}
        and bool(_message_text(message))
        for message in messages
    ):
        raise ValueError("coding_request delegated task is required")
    execution_mode = request.get("execution_mode")
    if execution_mode not in {"read_only", "approval", "autonomous"}:
        raise ValueError("coding_request execution_mode is invalid")
    for field in ("workspace", "thread_identity", "user_identity"):
        value = request.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"coding_request {field} is required")
    model = request.get("model")
    if "model" not in request or (model is not None and not isinstance(model, str)):
        raise ValueError("coding_request model is invalid")
    coding_session_id = request.get("coding_session_id")
    if not isinstance(coding_session_id, str):
        raise ValueError("coding_request coding_session_id is invalid")
    return {
        "messages": list(messages),
        "workspace": request["workspace"],
        "model": model,
        "execution_mode": execution_mode,
        "thread_identity": request["thread_identity"],
        "user_identity": request["user_identity"],
        "coding_session_id": coding_session_id,
    }


def _final_coder_messages(messages: list[Any]) -> list[Any]:
    final_messages = [
        message
        for message in messages
        if (
            (message.get("role") if isinstance(message, dict) else message.type)
            in {"assistant", "ai"}
            and not (
                message.get("tool_calls", [])
                if isinstance(message, dict)
                else getattr(message, "tool_calls", [])
            )
        )
    ][-1:]
    if not final_messages:
        final_messages = [
            AIMessage(
                content="The coding agent did not return a final result (missing_final_result)."
            )
        ]
    attributed = []
    for message in final_messages:
        if isinstance(message, dict):
            replacement = dict(message)
            replacement["name"] = "coding"
        else:
            replacement = message.model_copy(update={"name": "coding"})
        attributed.append(replacement)
    return attributed


def _technical_report_voice_text(report: TechnicalReport) -> str:
    """Produce bounded, evidence-aware speech from the validated handoff only."""

    outcome = {
        "completed": "The requested coding work is complete.",
        "partial": "The requested coding work is only partially complete.",
        "blocked": "The requested coding work is blocked.",
        "failed": "The requested coding work failed.",
        "cancelled": "The requested coding work was cancelled.",
    }[report.completion_status]
    completed = [note.task for note in report.task_notes if note.status == "completed"]
    details = []
    if completed:
        details.append(f"Completed: {completed[0]}.")
    passed = [e.type.replace("_", " ") for e in report.validation_evidence if e.result == "passed"]
    failed = [e.type.replace("_", " ") for e in report.validation_evidence if e.result == "failed"]
    inconclusive = [
        evidence.type.replace("_", " ")
        for evidence in report.validation_evidence
        if evidence.result in {"not_run", "inconclusive"}
    ]
    if passed:
        details.append(f"Passed {passed[0]}.")
    if failed:
        details.append(f"Failed {failed[0]}.")
    if inconclusive:
        details.append(f"{inconclusive[0].capitalize()} was not conclusive.")
    # Deployment is never inferred from source checks. It is named only from its own evidence.
    deployment = [
        evidence for evidence in report.validation_evidence if evidence.type == "deployment_check"
    ]
    if deployment and deployment[0].result == "passed":
        details.append("The reported deployment check passed.")
    elif deployment and deployment[0].result != "passed":
        details.append("The reported deployment check did not pass.")
    concerns = []
    if report.blockers:
        concerns.append(f"Blocker: {report.blockers[0]}.")
    if report.remaining_authorization_needs:
        need = report.remaining_authorization_needs[0]
        concerns.append(f"Authorization still needed for {need.action}: {need.reason}.")
    if report.material_risks:
        concerns.append(f"Risk: {report.material_risks[0].risk}.")
    paragraph_one = " ".join([outcome, *details]).strip()
    return "\n\n".join(part for part in (paragraph_one, " ".join(concerns)) if part)[:12000]


def _invalid_coder_report_voice_text() -> str:
    return (
        "The coding result could not be verified from its required technical report. "
        "No completion or deployment claim can be made."
    )


def _project_coder_output(state: CoderBridgeState) -> CoderBridgeOutputState:
    final_messages = _final_coder_messages(list(state.get("messages", [])))
    status = state.get("coding_status", "error")
    if "missing_final_result" in str(getattr(final_messages[0], "content", "")):
        status = "error"
    result: CoderToJasperResult = {
        "messages": final_messages,
        "coding_session_id": state.get("coding_session_id", ""),
        "coding_status": status,
    }
    if state.get("workspace") is not None:
        result["workspace"] = state["workspace"]
    if state.get("execution_manifest") is not None:
        result["execution_manifest"] = state["execution_manifest"]
    if "technical_report" in state:
        result["technical_report"] = state["technical_report"]
    return {"coding_result": result}


def create_jasper_coder_bridge():
    graph = StateGraph(
        CoderBridgeState,
        input_schema=CoderBridgeInputState,
        output_schema=CoderBridgeOutputState,
    )
    graph.add_node("prepare_coder_input", _prepare_coder_input)
    graph.add_node("coder", create_coding_agent_graph())
    graph.add_node("project_coder_output", _project_coder_output)
    graph.add_edge(START, "prepare_coder_input")
    graph.add_edge("prepare_coder_input", "coder")
    graph.add_edge("coder", "project_coder_output")
    graph.add_edge("project_coder_output", END)
    return graph.compile()


def _prepare_jasper_input(state: JasperGraphState) -> dict[str, Any]:
    request = state.get("jasper_request")
    if not isinstance(request, dict):
        raise ValueError("jasper_request is required")
    return {
        key: request[key]
        for key in (
            "messages",
            "todos",
            "model",
            "workspace",
            "execution_manifest",
            "execution_mode",
            "thread_identity",
            "user_identity",
            "coding_session_id",
            "session_evidence",
            "session_document_ids",
        )
        if key in request
    }


async def _run_jasper(state: JasperGraphState) -> Command[Literal["jasper_output"]]:
    result = await call_jasper(state)
    return Command(goto="jasper_output", update=result)


def _normal_jasper_output(state: JasperGraphState) -> JasperGraphOutputState:
    result: JasperGraphResult = {
        "route": "record_session",
        "messages": _messages_to_dicts(list(state.get("messages", []))[-1:]),
    }
    for key in (
        "jasper_response",
        "jasper_structured_response",
        "visual_artifacts",
        "layout_suggestion",
        "jasper_strategy",
        "jasper_diagnostic",
        "workspace",
        "execution_manifest",
        "session_document_ids",
    ):
        if key in state:
            result[key] = state[key]
    return {"jasper_result": result}


def _coder_jasper_output(state: JasperGraphState) -> JasperGraphOutputState:
    """Consume Coder's typed handoff; legacy assistant text is never a fallback."""

    coding_result = dict(state.get("coding_result") or {})
    raw_report = coding_result.get("technical_report")
    try:
        report = TechnicalReport.model_validate(raw_report)
        voice_text = _technical_report_voice_text(report)
        # The report is authoritative. Preserve legacy status values where they
        # have an equivalent, while retaining an observable cancelled outcome.
        coding_status = {
            "completed": "completed",
            "partial": "blocked",
            "blocked": "blocked",
            "failed": "error",
            "cancelled": "cancelled",
        }[report.completion_status]
        structured_response = JasperResponse(voice_text=voice_text).model_dump(mode="json")
        report_value: TechnicalReport | dict[str, Any] = report
    except Exception:
        logger.warning("Coder technical report validation failed")
        voice_text = _invalid_coder_report_voice_text()
        coding_status = "error"
        structured_response = JasperResponse(voice_text=voice_text).model_dump(mode="json")
        report_value = raw_report if isinstance(raw_report, dict) else {}
    result: JasperGraphResult = {
        "route": "record_session",
        "messages": [{"role": "assistant", "content": voice_text, "name": "jasper"}],
        "jasper_response": voice_text,
        "jasper_structured_response": structured_response,
        "coding_session_id": coding_result.get("coding_session_id", ""),
        "coding_status": coding_status,
        "technical_report": report_value,
    }
    if coding_result.get("workspace") is not None:
        result["workspace"] = coding_result["workspace"]
    if coding_result.get("execution_manifest") is not None:
        result["execution_manifest"] = coding_result["execution_manifest"]
    return {"jasper_result": result}


def _handoff_messages(state: JasperGraphState) -> list[dict]:
    messages = list(state.get("messages", []))
    if messages and isinstance(messages[-1], ToolMessage):
        return _messages_to_dicts(messages[-2:])
    return []


def _librarian_jasper_output(state: JasperGraphState) -> JasperGraphOutputState:
    return {
        "jasper_result": {
            "route": "librarian",
            "messages": _handoff_messages(state),
            "librarian_task": state.get("librarian_task", ""),
        }
    }


def _ocr_jasper_output(state: JasperGraphState) -> JasperGraphOutputState:
    return {
        "jasper_result": {
            "route": "ocr",
            "messages": _handoff_messages(state),
            "ocr_task": state.get("ocr_task", ""),
            "ocr_document_ref": state.get("ocr_document_ref", ""),
            "ocr_output_format": state.get("ocr_output_format", "markdown"),
        }
    }


def create_jasper_graph():
    coder_bridge = create_jasper_coder_bridge()
    graph = StateGraph(
        JasperGraphState,
        input_schema=JasperGraphInputState,
        output_schema=JasperGraphOutputState,
    )
    graph.add_node("prepare_jasper_input", _prepare_jasper_input)
    graph.add_node("call_jasper", _run_jasper)
    graph.add_node("coder_bridge", coder_bridge)
    graph.add_node("coder_output", _coder_jasper_output)
    graph.add_node("jasper_output", _normal_jasper_output)
    graph.add_node("librarian_exit", _librarian_jasper_output)
    graph.add_node("ocr_exit", _ocr_jasper_output)
    graph.add_edge(START, "prepare_jasper_input")
    graph.add_edge("prepare_jasper_input", "call_jasper")
    graph.add_edge("coder_bridge", "coder_output")
    graph.add_edge("coder_output", END)
    graph.add_edge("jasper_output", END)
    graph.add_edge("librarian_exit", END)
    graph.add_edge("ocr_exit", END)
    return graph.compile()
