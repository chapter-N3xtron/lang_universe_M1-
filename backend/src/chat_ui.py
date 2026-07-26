import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.agent_utils import get_user_query, get_conversation_history
from src.jasper_agent import create_jasper_graph
from src.llm import get_llm
from src.magic_coder_agent import run_magic_coder
from src.opencode_agent import create_opencode_graph
from src.research_agent import create_research_graph


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    workspace: str
    target_agent: str
    mode: str
    model: str
    opencode_session_id: str
    active_agent: str
    handoff_history: Annotated[list[dict], operator.add]
    decision_log: Annotated[list[dict], operator.add]
    pending_approval: bool
    pending_agent: str


AGENT_ROUTING = {
    "opencode": "opencode",
    "research": "research",
    "jasper": "jasper",
    "magic-coder": "magic-coder",
    "magic_coder": "magic-coder",
    "uncensored-coder": "magic-coder",
}

SUPERVISOR_PROMPT = """You are a supervisor agent managing a team of specialists. Your job is to decide which specialist should handle the user's request.

Available specialists:
- jasper: general daily assistant, ticketing, record keeping, friendly conversation
- opencode: coding, repository work, data visualization, file operations
- research: web research, essay analysis, structured Q&A, document breakdown
- magic-coder: image generation, ComfyUI workflows, creative work, character creation

Rules:
1. If the user explicitly asks for a specific agent, route to that agent.
2. If the user's request involves coding, repos, or data viz, route to opencode.
3. If the user's request involves research, web search, or document analysis, route to research.
4. If the user's request involves image generation, ComfyUI, or creative work, route to magic-coder.
5. For general conversation, questions, or assistance, route to jasper.
6. If the task appears complete and no further specialist work is needed, reply with "done".

Reply with ONLY the specialist name (jasper, opencode, research, magic-coder) or "done". No other text."""


def supervisor_node(state: State):
    target = (state.get("target_agent") or "").lower()
    if target in AGENT_ROUTING:
        node_name = AGENT_ROUTING[target]
        return Command(
            goto=node_name,
            update={
                "target_agent": "",
                "active_agent": target,
                "handoff_history": [{"from": "supervisor", "to": target, "reason": f"User requested {target}"}],
                "decision_log": [{"decision": f"route_to_{target}", "reason": f"User set target_agent={target}"}],
                "pending_approval": False,
            },
        )

    messages = state["messages"]
    history = get_conversation_history(messages)

    try:
        llm = get_llm()
        response = llm.invoke([{"role": "system", "content": SUPERVISOR_PROMPT}] + history)
        decision = response.content.strip().lower().rstrip(".")
    except Exception:
        decision = "jasper"

    if decision == "done" or decision == "":
        return {"pending_approval": False}

    node_name = AGENT_ROUTING.get(decision)
    if node_name is None:
        return {"active_agent": "", "pending_approval": False}

    return Command(
        goto="approval",
        update={
            "pending_agent": decision,
            "pending_approval": True,
            "decision_log": [{"decision": f"route_to_{decision}", "reason": f"LLM decided: {decision}"}],
        },
    )


def approval_node(state: State):
    agent = state.get("pending_agent", "")
    approved = interrupt({
        "question": f"Route to {agent} agent?",
        "agent": agent,
        "reason": f"Supervisor decided: {agent}",
    })
    if not approved:
        return {"pending_approval": False, "pending_agent": ""}
    node_name = AGENT_ROUTING.get(agent, "jasper")
    return Command(
        goto=node_name,
        update={
            "active_agent": agent,
            "handoff_history": [{"from": "supervisor", "to": agent, "reason": f"Supervisor routed to {agent} (approved)"}],
            "pending_approval": False,
            "pending_agent": "",
        },
    )


def create_chat_ui():
    graph = StateGraph(State)

    jasper_app = create_jasper_graph()
    opencode_app = create_opencode_graph()
    research_app = create_research_graph()

    def run_jasper(state):
        result = jasper_app.invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    def run_opencode(state):
        result = opencode_app.invoke({
            "messages": state["messages"],
            "workspace": state.get("workspace"),
            "mode": state.get("mode", "live"),
            "opencode_session_id": state.get("opencode_session_id"),
        })
        return {
            "messages": result["messages"],
            "opencode_session_id": result.get("opencode_session_id"),
        }

    def run_research(state):
        result = research_app.invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    def run_magic_coder_node(state):
        messages = state["messages"]
        user_query = get_user_query(messages)
        history = get_conversation_history(messages)

        mode = state.get("mode", "live")
        if mode == "async":
            from src.jobs import create_job, run_job
            job_id = create_job()
            run_job(
                job_id,
                lambda: run_magic_coder(
                    message=user_query,
                    history=history,
                    model=state.get("model"),
                    workspace=state.get("workspace"),
                )["text"],
            )
            content = f"[Magic Coder async job started]\n\nJob ID: {job_id}\nPoll /api/jobs/{job_id} for results."
        else:
            result = run_magic_coder(
                message=user_query,
                history=history,
                model=state.get("model"),
                workspace=state.get("workspace"),
            )
            if not result["success"]:
                content = f"[Magic Coder error]\n\n{result['error'] or 'Unknown error'}"
            else:
                content = result["text"] or "(no response)"
        return {"messages": [{"role": "assistant", "content": content}]}

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("approval", approval_node)
    graph.add_node("jasper", run_jasper)
    graph.add_node("opencode", run_opencode)
    graph.add_node("research", run_research)
    graph.add_node("magic-coder", run_magic_coder_node)

    graph.add_edge(START, "supervisor")

    for specialist in ["jasper", "opencode", "research", "magic-coder"]:
        graph.add_edge(specialist, "supervisor")

    return graph


def chat():
    app = create_chat_ui()
    messages = []

    dark_mode = {
        "header": "\033[1;36m",
        "user": "\033[1;32m",
        "assistant": "\033[1;33m",
        "error": "\033[1;31m",
        "reset": "\033[0m",
        "dim": "\033[2m"
    }

    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}")
    print(f"{dark_mode['header']}  LangGraph Agent Chat UI - Supervisor Mode{dark_mode['reset']}")
    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}")
    print(f"{dark_mode['dim']}  Agents: Jasper | OpenCode | Magic Coder | Research{dark_mode['reset']}")
    print(f"{dark_mode['dim']}  Type 'quit' to exit | 'clear' to clear history{dark_mode['reset']}")
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
        result = app.invoke({"messages": messages})

        assistant_msg = result["messages"][-1]["content"]
        active = result.get("active_agent", "unknown")
        print(f"\n{dark_mode['assistant']}[{active}]:{dark_mode['reset']} {assistant_msg}\n")
        messages.append({"role": "assistant", "content": assistant_msg})


if __name__ == "__main__":
    chat()
