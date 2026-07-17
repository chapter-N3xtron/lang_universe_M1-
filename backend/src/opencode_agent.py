from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, List
import operator

from src.opencode_cli import run_opencode


class State(TypedDict):
    messages: Annotated[List[dict], operator.add]
    code_response: str
    reasoning: str


def opencode_coding_agent(state: State):
    """OpenCode CLI agent - invokes the real opencode CLI binary."""
    messages = state["messages"]
    user_query = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            user_query = m.get("content", "")
            break

    try:
        result = run_opencode(
            message=user_query,
            title=user_query[:50],
        )

        if not result["success"]:
            content = f"""[OpenCode CLI error]

{result['error'] or 'Unknown error'}

Session: {result.get('session_id') or 'none'}
"""
        else:
            content = result["text"] or "(OpenCode CLI completed with no text output)"
            if result.get("artifacts"):
                content += "\n\n---\n\n**Tool outputs:**\n"
                for artifact in result["artifacts"]:
                    content += f"- `{artifact}`\n"
            if result.get("session_id"):
                content += f"\n_OpenCode session: {result['session_id']}_"

        return {
            "messages": [{"role": "assistant", "content": content}],
            "code_response": content,
            "reasoning": f"opencode run session={result.get('session_id')}",
        }
    except Exception as e:
        error_msg = f"""[OpenCode CLI Agent]

Error: {str(e)}

Please verify that the opencode CLI is installed and on PATH.
"""
        return {
            "messages": [{"role": "assistant", "content": error_msg}],
            "code_response": error_msg,
            "reasoning": "error",
        }


def create_opencode_graph():
    graph = StateGraph(State)
    graph.add_node("opencode_agent", opencode_coding_agent)
    graph.add_edge(START, "opencode_agent")
    graph.add_edge("opencode_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_opencode_graph()
    result = app.invoke({"messages": [{"role": "user", "content": "List the files in this project"}]})
    print(result["code_response"])
