import asyncio
import json
import operator
import os
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from src.agent_utils import get_conversation_history, get_user_query
from src.jasper_agent import STANDARD_SESSION_GREETING, create_jasper_graph
from src.librarian_agent import librarian_agent
from src.llm import get_llm
from src.magic_coder_graph import create_magic_coder_graph
from src.ocr_agent import run_ocr, specialist_message
from src.runtime_authority import authoritative_thread_id
from src.session_catalog import record_session_projection
from src.workspace_policy import (
    ExecutionManifest,
    WorkspacePolicyError,
    canonical_workspace,
    execution_manifest,
)


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    workspace: str
    target_agent: str
    mode: str
    model: str
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    execution_manifest: ExecutionManifest
    coding_task: str
    jasper_request: dict
    jasper_result: dict
    jasper_response: str
    jasper_structured_response: dict
    visual_artifacts: list[dict]
    layout_suggestion: dict | None
    jasper_strategy: str
    jasper_diagnostic: dict | None
    active_agent: str
    handoff_history: Annotated[list[dict], operator.add]
    decision_log: Annotated[list[dict], operator.add]
    pending_approval: bool
    pending_agent: str
    todos: list[dict]
    session_event: str
    session_opened: bool
    session_opening_version: str
    librarian_task: str
    ocr_task: str
    ocr_document_ref: str
    ocr_output_format: str
    session_evidence: Annotated[list[dict], operator.add]
    ui: Annotated[list[AnyUIMessage], ui_message_reducer]


TODOS_FILE = os.getenv(
    "TODOS_FILE", str(Path(__file__).resolve().parent.parent.parent / "todos.json")
)


def _load_todos() -> list[dict]:
    try:
        with open(TODOS_FILE) as f:
            data = json.load(f)
            return data.get("sections", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def session_opening_node(state: State) -> dict:
    """Return the canonical opening without invoking a model.

    The opening is a durable state transition, so make the node idempotent as
    well as guarding it in the supervisor. This matters if two open/reopen
    requests race before ``session_opened`` is visible in a checkpoint.
    """

    existing_messages = state.get("messages", [])
    already_greeted = any(
        message.get("role") == "assistant"
        and message.get("content") == STANDARD_SESSION_GREETING
        for message in existing_messages
        if isinstance(message, dict)
    )
    return {
        "messages": []
        if already_greeted
        else [{"role": "assistant", "content": STANDARD_SESSION_GREETING}],
        "active_agent": "jasper",
        "session_opened": True,
        "session_opening_version": "2026-08-03.1",
    }


AGENT_ROUTING = {
    "coding": "jasper",
    "deep-agent": "jasper",
    "deepagents": "jasper",
    "research": "librarian",
    "librarian": "librarian",
    "jasper": "jasper",
    "magic-coder": "magic-coder",
    "magic_coder": "magic-coder",
    "ocr": "ocr",
    "uncensored-coder": "magic-coder",
}


def _entry_node(agent: str) -> str:
    return "prepare_jasper" if agent == "jasper" else agent


SUPERVISOR_PROMPT = """You are a supervisor agent managing a team of specialists. Your job is to decide which specialist should handle the user's request.

Available specialists:
- jasper: general daily assistant, ticketing, record keeping, friendly conversation
- coding: repository analysis and coding work through Deep Agents
- librarian: web research, essay analysis, structured Q&A, document breakdown
- magic-coder: image generation, ComfyUI workflows, creative work, character creation
- ocr: Docling layout parsing and verified document OCR

Rules:
1. If the user explicitly asks for a specific agent, route to that agent.
2. If the user's request involves coding or repositories, route to coding.
3. If the user's request involves research, web search, or document analysis, route to librarian.
4. If the user's request involves image generation, ComfyUI, or creative work, route to magic-coder.
5. For general conversation, questions, or assistance, route to jasper.
6. If the task appears complete and no further specialist work is needed, reply with "done".

Reply with ONLY the specialist name (jasper, coding, librarian, magic-coder, ocr) or "done". No other text."""


def supervisor_node(
    state: State,
) -> (
    Command[
        Literal[
            "session_opening",
            "approval",
            "prepare_jasper",
            "librarian",
            "magic-coder",
            "ocr",
        ]
    ]
    | dict
):
    todos_data = _load_todos()
    messages = state["messages"]
    history = get_conversation_history(messages)

    if state.get("session_event") == "open" and not state.get("session_opened"):
        return Command(goto="session_opening", update={"todos": todos_data})

    # Specialist nodes return here through static edges. Finish the turn before
    # considering a sticky user-selected agent, otherwise an explicit selection
    # would route forever.
    if history and history[-1]["role"] == "assistant":
        return {
            "pending_approval": False,
            "pending_agent": "",
            "active_agent": "",
            "decision_log": [
                {"decision": "done", "reason": "Specialist already responded"}
            ],
            "todos": todos_data,
        }

    target = (state.get("target_agent") or "").lower()
    if target in AGENT_ROUTING:
        node_name = AGENT_ROUTING[target]
        return Command(
            goto=_entry_node(node_name),
            update={
                "active_agent": node_name,
                "handoff_history": [
                    {
                        "from": "supervisor",
                        "to": node_name,
                        "reason": f"User requested {target}",
                    }
                ],
                "decision_log": [
                    {
                        "decision": f"route_to_{node_name}",
                        "reason": f"User set target_agent={target}",
                    }
                ],
                "pending_approval": False,
                "todos": todos_data,
            },
        )

    user_text = get_user_query(messages).lower()
    if any(
        phrase in user_text
        for phrase in ("concept map", "flowchart", "flow chart", "draw a diagram")
    ):
        decision = "jasper"
        reason = "Deterministic visual-artifact ownership"
    else:
        try:
            llm = get_llm()
            response = llm.invoke(
                [{"role": "system", "content": SUPERVISOR_PROMPT}] + history
            )
            decision = response.content.strip().lower().rstrip(".")
        except Exception:
            decision = "jasper"
        reason = f"LLM decided: {decision}"

    # Fallback: never end the graph without producing a response.
    # If the LLM says "done" or returns an unrecognized name, default to jasper
    # so the user always gets a reply.
    if decision == "done" or decision == "":
        decision = "jasper"

    node_name = AGENT_ROUTING.get(decision)
    if node_name is None:
        node_name = "jasper"
    decision = node_name

    if state.get("execution_mode") == "autonomous":
        return Command(
            goto=_entry_node(node_name),
            update={
                "active_agent": decision,
                "pending_agent": "",
                "pending_approval": False,
                "handoff_history": [
                    {
                        "from": "supervisor",
                        "to": decision,
                        "reason": "Autonomous execution mode",
                    }
                ],
                "decision_log": [
                    {"decision": f"route_to_{decision}", "reason": reason}
                ],
                "todos": todos_data,
            },
        )

    return Command(
        goto="approval",
        update={
            "pending_agent": decision,
            "pending_approval": True,
            "decision_log": [{"decision": f"route_to_{decision}", "reason": reason}],
            "todos": todos_data,
        },
    )


def _is_approved(resume_value) -> bool:
    """Handle both the new HITL Decision dict and the legacy boolean resume."""
    if isinstance(resume_value, dict):
        if "decisions" in resume_value:
            decisions = resume_value["decisions"]
            if isinstance(decisions, list):
                return any(
                    isinstance(d, dict) and d.get("type") == "approve"
                    for d in decisions
                )
        return resume_value.get("type") == "approve"
    if isinstance(resume_value, list):
        return any(
            isinstance(d, dict) and d.get("type") == "approve" for d in resume_value
        )
    return bool(resume_value)


def approval_node(
    state: State,
) -> Command[Literal["prepare_jasper", "librarian", "magic-coder", "ocr"]] | dict:
    agent = state.get("pending_agent", "")
    approved = interrupt(
        {
            "action_requests": [
                {
                    "name": f"route_to_{agent}",
                    "args": {
                        "agent": agent,
                        **(
                            {"task": state.get("coding_task", "")}
                            if agent == "coding"
                            else {}
                        ),
                    },
                    "description": (
                        f"Allow Coding to begin: {state.get('coding_task', '')}"
                        if agent == "coding"
                        else f"Route this conversation to the {agent} agent?"
                    ),
                }
            ],
            "review_configs": [
                {
                    "action_name": f"route_to_{agent}",
                    "allowed_decisions": ["approve", "reject"],
                }
            ],
        }
    )
    if not _is_approved(approved):
        return {
            "pending_approval": False,
            "pending_agent": "",
            "coding_task": "" if agent == "coding" else state.get("coding_task", ""),
        }
    node_name = AGENT_ROUTING.get(agent, "jasper")
    return Command(
        goto=_entry_node(node_name),
        update={
            "active_agent": node_name,
            "handoff_history": [
                {
                    "from": "supervisor",
                    "to": node_name,
                    "reason": f"Supervisor routed to {node_name} (approved)",
                }
            ],
            "pending_approval": False,
            "pending_agent": "",
        },
    )


def _base_messages_to_dicts(messages: list) -> list[dict]:
    role_map = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    result = []
    for m in messages:
        if isinstance(m, dict):
            result.append(m)
            continue
        msg_type = getattr(m, "type", "")
        role = role_map.get(msg_type, msg_type)
        entry = {"role": role, "content": getattr(m, "content", "")}
        if getattr(m, "name", None):
            entry["name"] = m.name
        if role == "assistant" and hasattr(m, "tool_calls") and m.tool_calls:
            entry["tool_calls"] = m.tool_calls
        if role == "assistant" and getattr(m, "additional_kwargs", None):
            entry["additional_kwargs"] = m.additional_kwargs
        if role == "tool":
            entry["tool_call_id"] = getattr(m, "tool_call_id", "")
        result.append(entry)
    return result


def create_chat_ui():
    graph = StateGraph(State)

    jasper_app = create_jasper_graph()
    magic_coder_app = create_magic_coder_graph()

    def prepare_jasper(
        state, config: RunnableConfig
    ) -> Command[Literal["jasper", "record_session"]]:
        configurable = config.get("configurable", {})
        thread_id = authoritative_thread_id(
            state.get("thread_identity"),
            config,
            operation="prepare_jasper",
        )
        try:
            workspace = (
                canonical_workspace(state.get("workspace"))
                if state.get("workspace")
                else None
            )
        except WorkspacePolicyError:
            return Command(
                goto="record_session",
                update={
                    "messages": [
                        {
                            "role": "assistant",
                            "name": "jasper",
                            "content": (
                                "The selected workspace is unavailable or unauthorized "
                                "(invalid_workspace). No substitute workspace was used."
                            ),
                        }
                    ]
                },
            )
        manifest = execution_manifest(workspace) if workspace is not None else None
        request = {
            "messages": state["messages"],
            "todos": state.get("todos", []),
            "model": state.get("model"),
            "workspace": str(workspace) if workspace is not None else "",
            "execution_mode": state.get("execution_mode") or state.get("mode"),
            "thread_identity": thread_id,
            "user_identity": state.get("user_identity")
            or configurable.get("user_id")
            or configurable.get("owner_id")
            or "anonymous",
            "coding_session_id": thread_id,
            "session_evidence": state.get("session_evidence", []),
        }
        if manifest is not None:
            request["execution_manifest"] = manifest
        return Command(goto="jasper", update={"jasper_request": request})

    def route_jasper_result(
        state,
    ) -> Command[Literal["librarian", "ocr", "record_session"]]:
        result = dict(state.get("jasper_result") or {})
        route = result.pop("route", "record_session")
        messages = result.pop("messages", [])
        update = {
            **result,
            "messages": messages,
            "jasper_request": {},
            "jasper_result": {},
        }
        if "coding_status" in result:
            update["coding_task"] = ""
        if route == "librarian":
            return Command(goto="librarian", update=update)
        if route == "ocr":
            return Command(goto="ocr", update=update)
        return Command(goto="record_session", update=update)

    async def run_librarian(
        state, config: RunnableConfig
    ) -> Command[Literal["prepare_jasper", "record_session"]]:
        handed_off_task = bool((state.get("librarian_task") or "").strip())
        result = await librarian_agent(state, config)
        return Command(
            goto="prepare_jasper" if handed_off_task else "record_session",
            update={
                "messages": _base_messages_to_dicts(result.get("messages", [])),
                "librarian_task": "",
            },
        )

    async def run_ocr_node(
        state,
    ) -> Command[Literal["record_session"]]:
        output_format = state.get("ocr_output_format", "markdown")
        try:
            result = await asyncio.to_thread(
                run_ocr,
                state.get("ocr_task", ""),
                state.get("ocr_document_ref", ""),
                state.get("workspace"),
                output_format,
            )
            message = {
                "role": "assistant",
                "name": "ocr",
                "content": specialist_message(result, output_format),
            }
        except Exception as exc:
            message = {
                "role": "assistant",
                "name": "ocr",
                "content": f"OCR failed: {exc}",
            }
        return Command(
            goto="record_session",
            update={
                "messages": [message],
                "ocr_task": "",
                "ocr_document_ref": "",
            },
        )

    async def run_magic_coder_node(state):
        input_count = len(state["messages"])
        result = await magic_coder_app.ainvoke(
            {
                "messages": state["messages"],
                "workspace": state.get("workspace"),
                "mode": state.get("mode", "live"),
                "model": state.get("model"),
            }
        )
        new_messages = result["messages"][input_count:]
        return {"messages": _base_messages_to_dicts(new_messages)}

    async def record_session(
        state: State, config: RunnableConfig, runtime: Runtime
    ) -> dict:
        """Persist the completed turn without adding another model call."""

        try:
            workspace = (
                canonical_workspace(state.get("workspace"))
                if state.get("workspace")
                else None
            )
        except WorkspacePolicyError:
            await record_session_projection(state, config, runtime)
            return {}
        manifest = execution_manifest(workspace) if workspace is not None else None
        projection_state = dict(state)
        if workspace is not None and manifest is not None:
            projection_state.update(
                {
                    "workspace": str(workspace),
                    "execution_manifest": manifest,
                }
            )
        await record_session_projection(projection_state, config, runtime)
        if workspace is None or manifest is None:
            return {}
        return {
            "workspace": str(workspace),
            "execution_manifest": manifest,
        }

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("session_opening", session_opening_node)
    graph.add_node("approval", approval_node)
    graph.add_node("prepare_jasper", prepare_jasper)
    graph.add_node("jasper", jasper_app)
    graph.add_node("route_jasper_result", route_jasper_result)
    graph.add_node("librarian", run_librarian)
    graph.add_node("ocr", run_ocr_node)
    graph.add_node("magic-coder", run_magic_coder_node)
    graph.add_node("record_session", record_session)

    graph.add_edge(START, "supervisor")
    graph.add_edge("session_opening", "record_session")
    graph.add_edge("jasper", "route_jasper_result")

    graph.add_edge("magic-coder", "record_session")
    graph.add_edge("record_session", END)

    return graph


async def chat():
    app = create_chat_ui()
    messages = []

    dark_mode = {
        "header": "\033[1;36m",
        "user": "\033[1;32m",
        "assistant": "\033[1;33m",
        "error": "\033[1;31m",
        "reset": "\033[0m",
        "dim": "\033[2m",
    }

    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}")
    print(
        f"{dark_mode['header']}  LangGraph Agent Chat UI - Supervisor Mode{dark_mode['reset']}"
    )
    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}")
    print(
        f"{dark_mode['dim']}  Agents: Jasper | The Librarian | Magic Coder{dark_mode['reset']}"
    )
    print(
        f"{dark_mode['dim']}  Type 'quit' to exit | 'clear' to clear history{dark_mode['reset']}"
    )
    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}\n")

    while True:
        try:
            user_input = input(f"{dark_mode['user']}You:{dark_mode['reset']} ").strip()
        except EOFError:
            break

        if user_input.lower() in ["quit", "exit"]:
            print(f"{dark_mode['dim']}Goodbye!{dark_mode['reset']}")
            break

        if user_input.lower() == "clear":
            messages = []
            print(f"{dark_mode['dim']}Chat history cleared.{dark_mode['reset']}\n")
            continue

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        result = await app.ainvoke({"messages": messages})

        assistant_msg = result["messages"][-1]["content"]
        active = result.get("active_agent", "unknown")
        print(
            f"\n{dark_mode['assistant']}[{active}]:{dark_mode['reset']} {assistant_msg}\n"
        )
        messages.append({"role": "assistant", "content": assistant_msg})


if __name__ == "__main__":
    asyncio.run(chat())
