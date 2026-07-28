import operator
from typing import Annotated, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from src.agent_utils import get_user_query, get_conversation_history
from src.opencode_cli import run_opencode, run_opencode_stream


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    workspace: str
    mode: str
    model: str
    code_response: str
    reasoning: str
    opencode_session_id: str


async def opencode_coding_agent(state: State):
    """OpenCode CLI agent — invokes the real opencode CLI binary, streaming."""
    messages = state["messages"]
    user_query = get_user_query(messages)

    try:
        workspace = state.get("workspace")
        mode = state.get("mode", "live")
        prior_session_id = state.get("opencode_session_id")

        history_for_model = get_conversation_history(messages)
        writer = get_stream_writer()
        text_parts: list[str] = []
        found_session_id: str | None = None
        artifacts: list[str] = []

        writer({"type": "status", "content": "running"})

        async for event in run_opencode_stream(
            message=user_query,
            title=user_query[:50],
            workspace=workspace,
            model=state.get("model"),
            auto_approve=(mode == "async"),
            history=history_for_model,
            session_id=prior_session_id,
        ):
            if not event.get("type"):
                continue

            if event["type"] == "text":
                chunk = event.get("text", "")
                text_parts.append(chunk)
                writer({"type": "text", "content": chunk})
            elif event["type"] == "complete":
                found_session_id = event.get("session_id") or prior_session_id
                artifacts = event.get("artifacts", [])
            elif event["type"] == "error":
                content = f"""[OpenCode CLI error]

{event.get('error', 'Unknown error')}

Session: {found_session_id or 'none'}
"""
                writer({"type": "error", "content": content})
                return {
                    "messages": [{"role": "assistant", "content": content}],
                    "code_response": content,
                    "reasoning": "error",
                    "opencode_session_id": found_session_id or prior_session_id,
                }

        writer({"type": "complete", "content": ""})

        content = "".join(text_parts) or "(OpenCode CLI completed with no text output)"
        if artifacts:
            content += "\n\n---\n\n**Tool outputs:**\n"
            for artifact in artifacts:
                content += f"- `{artifact}`\n"
        if found_session_id:
            content += f"\n_OpenCode session: {found_session_id}_"

        return {
            "messages": [{"role": "assistant", "content": content}],
            "code_response": content,
            "reasoning": f"opencode run session={found_session_id}",
            "opencode_session_id": found_session_id or prior_session_id,
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
