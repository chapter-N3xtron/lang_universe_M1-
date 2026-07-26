import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agent_utils import get_user_query, get_conversation_history
from src.magic_coder_agent import run_magic_coder


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    workspace: str
    mode: str
    model: str
    code_response: str


def magic_coder_node(state: State):
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
    return {"messages": [{"role": "assistant", "content": content}], "code_response": content}


def create_magic_coder_graph():
    graph = StateGraph(State)
    graph.add_node("magic_coder_agent", magic_coder_node)
    graph.add_edge(START, "magic_coder_agent")
    graph.add_edge("magic_coder_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_magic_coder_graph()
    result = app.invoke({
        "messages": [{"role": "user", "content": "List the files in the current directory"}],
        "workspace": "/tmp",
        "mode": "live",
        "model": None,
    })
    print(result["code_response"])
