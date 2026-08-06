import asyncio
import json
import operator
import os
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from src.agent_utils import get_conversation_history, get_user_query
from src.coding_agent import create_coding_agent_graph
from src.jasper_agent import STANDARD_SESSION_GREETING, call_jasper
from src.librarian_agent import librarian_agent
from src.llm import get_llm
from src.magic_coder_graph import create_magic_coder_graph
from src.research_agent import research_agent
from src.session_catalog import record_session_projection


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
    coding_events: list[dict]
    coding_task: str
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
    research_task: str
    session_evidence: Annotated[list[dict], operator.add]


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


def session_opening_node(_state: State) -> dict:
    """Return the canonical opening without invoking a model."""

    return {
        "messages": [{"role": "assistant", "content": STANDARD_SESSION_GREETING}],
        "active_agent": "jasper",
        "session_opened": True,
        "session_opening_version": "2026-08-03.1",
    }


AGENT_ROUTING = {
    "coding": "coding",
    "deep-agent": "coding",
    "deepagents": "coding",
    "research": "research",
    "librarian": "librarian",
    "jasper": "jasper",
    "magic-coder": "magic-coder",
    "magic_coder": "magic-coder",
    "uncensored-coder": "magic-coder",
}

SUPERVISOR_PROMPT = """You are a supervisor agent managing a team of specialists. Your job is to decide which specialist should handle the user's request.

Available specialists:
- jasper: general daily assistant, ticketing, record keeping, friendly conversation
- coding: repository analysis and coding work through Deep Agents
- research: web research, essay analysis, structured Q&A, document breakdown
- magic-coder: image generation, ComfyUI workflows, creative work, character creation

Rules:
1. If the user explicitly asks for a specific agent, route to that agent.
2. If the user's request involves coding or repositories, route to coding.
3. If the user's request involves research, web search, or document analysis, route to research.
4. If the user's request involves image generation, ComfyUI, or creative work, route to magic-coder.
5. For general conversation, questions, or assistance, route to jasper.
6. If the task appears complete and no further specialist work is needed, reply with "done".

Reply with ONLY the specialist name (jasper, coding, research, magic-coder) or "done". No other text."""


def supervisor_node(
    state: State,
) -> (
    Command[
        Literal[
            "session_opening",
            "approval",
            "jasper",
            "coding",
            "research",
            "librarian",
            "magic-coder",
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
            goto=node_name,
            update={
                "active_agent": target,
                "handoff_history": [
                    {
                        "from": "supervisor",
                        "to": target,
                        "reason": f"User requested {target}",
                    }
                ],
                "decision_log": [
                    {
                        "decision": f"route_to_{target}",
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
        decision = "jasper"
        node_name = "jasper"

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
) -> (
    Command[Literal["jasper", "coding", "research", "librarian", "magic-coder"]] | dict
):
    agent = state.get("pending_agent", "")
    approved = interrupt(
        {
            "action_requests": [
                {
                    "name": f"route_to_{agent}",
                    "args": {"agent": agent},
                    "description": f"Route this conversation to the {agent} agent?",
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
        return {"pending_approval": False, "pending_agent": ""}
    node_name = AGENT_ROUTING.get(agent, "jasper")
    return Command(
        goto=node_name,
        update={
            "active_agent": agent,
            "handoff_history": [
                {
                    "from": "supervisor",
                    "to": agent,
                    "reason": f"Supervisor routed to {agent} (approved)",
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

    coding_app = create_coding_agent_graph()
    magic_coder_app = create_magic_coder_graph()

    async def run_jasper(
        state, config: RunnableConfig
    ) -> Command[Literal["coding", "research", "record_session"]]:
        latest = state.get("messages", [])[-1:] or [{}]
        latest = latest[0]
        latest_role = (
            latest.get("role") if isinstance(latest, dict) else latest.type
        )
        latest_name = (
            latest.get("name") if isinstance(latest, dict) else latest.name
        )
        if latest_role in {"assistant", "ai"} and latest_name == "coding":
            return Command(goto="record_session")

        configurable = config.get("configurable", {})
        result = await call_jasper(
            {
                "messages": state["messages"],
                "todos": state.get("todos", []),
                "model": state.get("model", ""),
                "workspace": state.get("workspace") or os.getcwd(),
                "execution_mode": state.get("execution_mode") or state.get("mode"),
                "thread_identity": state.get("thread_identity")
                or configurable.get("thread_id", ""),
                "user_identity": state.get("user_identity", "anonymous"),
                "coding_session_id": state.get("coding_session_id", ""),
                "session_evidence": state.get("session_evidence", []),
            }
        )
        return Command(
            goto="record_session",
            update={
                **result,
                "messages": _base_messages_to_dicts(result.get("messages", [])),
            },
        )

    async def run_coding(state, config: RunnableConfig) -> Command[Literal["jasper"]]:
        configurable = config.get("configurable", {})
        handed_off_task = (state.get("coding_task") or "").strip()
        task = handed_off_task or get_user_query(state.get("messages", []))
        execution_mode = state.get("execution_mode") or state.get("mode")
        if handed_off_task and execution_mode not in {"read_only", "approval"}:
            result = {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "The coding handoff is blocked because no explicit "
                            "execution mode was selected."
                        ),
                    }
                ],
                "coding_status": "error",
                "coding_events": [],
            }
        else:
            task_messages = [HumanMessage(content=task)]
            result = await coding_app.ainvoke(
                {
                    "messages": task_messages,
                    "workspace": state.get("workspace"),
                    "execution_mode": execution_mode or "approval",
                    "model": state.get("model"),
                    "thread_identity": state.get("thread_identity")
                    or configurable.get("thread_id", ""),
                    "user_identity": state.get("user_identity")
                    or configurable.get("user_id")
                    or configurable.get("owner_id")
                    or "anonymous",
                    "coding_session_id": state.get("coding_session_id") or "",
                },
                config=config,
            )
            result["messages"] = result.get("messages", [])[len(task_messages) :]
        final_messages = [
            message
            for message in result.get("messages", [])
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
        coding_status = result.get("coding_status", "error")
        if not final_messages:
            final_messages = [
                {
                    "role": "assistant",
                    "content": (
                        "The coding agent did not return a final result "
                        "(missing_final_result)."
                    ),
                }
            ]
            coding_status = "error"
        outer_messages = _base_messages_to_dicts(final_messages)
        for message in outer_messages:
            message["name"] = "coding"
        update = {
            "messages": outer_messages,
            "coding_task": "",
            "coding_session_id": result.get("coding_session_id", ""),
            "coding_status": coding_status,
            "coding_events": result.get("coding_events", []),
        }
        return Command(goto="jasper", update=update)

    async def run_research(
        state, config: RunnableConfig, runtime: Runtime
    ) -> Command[Literal["jasper"]] | dict:
        configurable = config.get("configurable", {})
        messages = (
            state["messages"][-2:] if state.get("research_task") else state["messages"]
        )
        result = await research_agent(
            {
                "messages": messages,
                "model": state.get("model", ""),
                "workspace": state.get("workspace") or os.getcwd(),
                "thread_identity": state.get("thread_identity")
                or configurable.get("thread_id", ""),
                "user_identity": state.get("user_identity")
                or configurable.get("user_id")
                or configurable.get("owner_id")
                or "anonymous",
                "session_evidence": state.get("session_evidence", []),
            },
            runtime,
        )
        update = {
            "messages": _base_messages_to_dicts(result.get("messages", [])[-1:]),
            "research_task": "",
            "session_evidence": result.get("session_evidence", []),
        }
        if state.get("research_task"):
            return Command(goto="jasper", update=update)
        return update

    async def run_librarian(state, config: RunnableConfig) -> dict:
        result = await librarian_agent(state, config)
        return {"messages": _base_messages_to_dicts(result.get("messages", []))}

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

        await record_session_projection(state, config, runtime)
        return {}

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("session_opening", session_opening_node)
    graph.add_node("approval", approval_node)
    graph.add_node("jasper", run_jasper)
    graph.add_node("coding", run_coding)
    graph.add_node("research", run_research)
    graph.add_node("librarian", run_librarian)
    graph.add_node("magic-coder", run_magic_coder_node)
    graph.add_node("record_session", record_session)

    graph.add_edge(START, "supervisor")
    graph.add_edge("session_opening", "record_session")

    for specialist in ["research", "librarian", "magic-coder"]:
        graph.add_edge(specialist, "record_session")
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
        f"{dark_mode['dim']}  Agents: Jasper | Coding | Magic Coder | Research{dark_mode['reset']}"
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
