from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from typing import Annotated, TypedDict

from src.agent_utils import get_user_query
from src.llm import get_llm
from src.jasper_tools import list_todos, read_file, web_search, read_url


class State(TypedDict):
    messages: Annotated[list, add_messages]
    jasper_response: str
    todos: list[dict]


ACTIVE_TOOLS = [list_todos, read_file, read_url]

def _active_tools():
    """Return tools available to Jasper, checking env at runtime."""
    tools = [list_todos, read_file, read_url]
    if __import__("os").getenv("TAVILY_API_KEY"):
        tools.append(web_search)
    return tools


def _format_todos_for_prompt(todos: list[dict]) -> str:
    if not todos:
        return "No todos currently tracked."
    lines = []
    for section in todos:
        model = section.get("planned_by_model", "unknown")
        lines.append(f"## {section['title']} (planned by {model})")
        for t in section.get("todos", []):
            mark = {"pending": "○", "in_progress": "◉", "completed": "✓"}.get(t["status"], "○")
            model_tag = f" [done by {t['completed_by_model']}]" if t.get("completed_by_model") else ""
            lines.append(f"  {mark} {t['content']}{model_tag}")
    return "\n".join(lines)


def call_model(state: State):
    messages = state["messages"]
    todos_data = state.get("todos", [])

    try:
        llm = get_llm().bind_tools(_active_tools())
        formatted_todos = _format_todos_for_prompt(todos_data)
        system_prompt = (
            "You are Jasper, a helpful daily-driver assistant. "
            "You can hand off tasks to OpenCode for coding/repo work, "
            "Research for web searches, or Magic Coder for unrestricted coding. "
            "Be concise and friendly.\n\n"
            "You have access to tools you can use to help the user. "
            "When the user asks about task status, what's been done, what model did what, "
            "or what's pending, use the list_todos tool.\n\n"
            f"CURRENT TODO LIST:\n{formatted_todos}"
        )
        full_messages = [SystemMessage(content=system_prompt)] + list(messages)
        response = llm.invoke(full_messages)
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

    result = {"messages": [response]}
    if not response.tool_calls:
        result["jasper_response"] = content
    return result


def create_jasper_graph():
    graph = StateGraph(State)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(_active_tools()))
    graph.add_conditional_edges("call_model", tools_condition)
    graph.add_edge("tools", "call_model")
    graph.add_edge(START, "call_model")
    return graph.compile()
