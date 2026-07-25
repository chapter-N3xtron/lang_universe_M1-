import operator
from typing import Annotated, TypedDict

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

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


def router(state: State):
    """Route deterministically by target_agent. Falls back to keyword heuristic only when missing."""
    target = (state.get("target_agent") or "").lower()
    if target == "opencode":
        return "opencode"
    if target == "uncensored-coder":
        return "magic-coder"
    if target == "research":
        return "research"
    if target == "jasper":
        return "jasper"

    # Fallback keyword heuristic for backwards compatibility
    user_messages = [m for m in state["messages"] if isinstance(m, dict) and m.get("role") == "user"]
    if not user_messages:
        return END
    content = user_messages[-1].get("content", "").lower()
    if any(word in content for word in ["code", "function", "class", "implement", "bug", "fix", "create", "write", "refactor", "add", "update", "delete", "test", "build", "repo"]):
        return "opencode"
    if any(word in content for word in ["research", "search", "find", "scrape", "crawl"]):
        return "research"
    return "jasper"


def jasper_agent(state: State):
    """Daily-driver assistant / ticket clerk. Simple echo with routing info for now."""
    user_messages = [m for m in state["messages"] if isinstance(m, dict) and m.get("role") == "user"]
    user_text = user_messages[-1].get("content", "") if user_messages else ""

    content = f"""Hi, I'm Jasper.

I heard: "{user_text}"

I can hand this off to OpenCode for repo work or Research for web tasks. Use the agent selector above to choose who should handle it."""

    return {
        "messages": [{"role": "assistant", "content": content}],
    }


def create_chat_ui(checkpointer=None):
    graph = StateGraph(State)

    opencode_app = create_opencode_graph()
    research_app = create_research_graph()

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
        user_query = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_query = m.get("content", "")
                break

        # Pass all prior user/assistant turns as history. The graph's checkpointer
        # already accumulated earlier messages, so this includes the full
        # conversation including the current turn.
        history = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in messages
            if isinstance(m, dict) and m.get("role") in ("user", "assistant")
        ]

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

    graph.add_node("jasper", jasper_agent)
    graph.add_node("opencode", run_opencode)
    graph.add_node("research", run_research)
    graph.add_node("magic-coder", run_magic_coder_node)

    graph.add_conditional_edges(START, router, ["jasper", "opencode", "magic-coder", "research", END])
    graph.add_edge("jasper", END)
    graph.add_edge("opencode", END)
    graph.add_edge("research", END)
    graph.add_edge("magic-coder", END)

    # Use the provided checkpointer, or fall back to in-memory for CLI usage.
    if checkpointer is None:
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def chat():
    """Interactive chat loop with dark mode UI"""
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
    print(f"{dark_mode['header']}  LangGraph Agent Chat UI - Dark Mode{dark_mode['reset']}")
    print(f"{dark_mode['header']}{'=' * 70}{dark_mode['reset']}")
    print(f"{dark_mode['dim']}  Agents: OpenCode (coding) | Magic Coder (unrestricted coding) | Research (web scraping){dark_mode['reset']}")
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
        print(f"\n{dark_mode['assistant']}Agent:{dark_mode['reset']} {assistant_msg}\n")
        messages.append({"role": "assistant", "content": assistant_msg})


if __name__ == "__main__":
    chat()
