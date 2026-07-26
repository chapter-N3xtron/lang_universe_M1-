from langgraph.graph import END, START, StateGraph
from typing import Annotated, TypedDict
import operator

from src.agent_utils import get_user_query, get_conversation_history
from src.llm import get_llm


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    jasper_response: str


def jasper_agent(state: State):
    messages = state["messages"]
    history = get_conversation_history(messages)

    system_prompt = (
        "You are Jasper, a helpful daily-driver assistant. "
        "You can hand off tasks to OpenCode for coding/repo work, "
        "Research for web searches, or Magic Coder for unrestricted coding. "
        "Be concise and friendly."
    )

    try:
        llm = get_llm()
        response = llm.invoke([{"role": "system", "content": system_prompt}] + history)
        content = response.content
    except Exception:
        user_text = get_user_query(messages)
        content = (
            f"Hi, I'm Jasper.\n\n"
            f"I heard: \"{user_text}\"\n\n"
            f"I can hand this off to OpenCode for repo work or Research for web tasks. "
            f"Use the agent selector above to choose who should handle it."
        )

    return {"messages": [{"role": "assistant", "content": content}], "jasper_response": content}


def create_jasper_graph():
    graph = StateGraph(State)
    graph.add_node("jasper_agent", jasper_agent)
    graph.add_edge(START, "jasper_agent")
    graph.add_edge("jasper_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_jasper_graph()
    result = app.invoke({"messages": [{"role": "user", "content": "Hello! What can you do?"}]})
    print(result["jasper_response"])
