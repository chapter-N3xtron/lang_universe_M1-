from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, List
import operator
from src.opencode_agent import create_opencode_graph
from src.research_agent import create_research_graph


class State(TypedDict):
    messages: Annotated[List[dict], operator.add]


def router(state: State):
    """Route the latest user message to the appropriate agent."""
    user_messages = [m for m in state["messages"] if isinstance(m, dict) and m.get("role") == "user"]
    if not user_messages:
        return END

    content = user_messages[-1].get("content", "").lower()

    if any(word in content for word in ["code", "function", "class", "implement", "bug", "fix", "create", "write"]):
        return "opencode"
    elif any(word in content for word in ["research", "search", "find", "scrape", "crawl"]):
        return "research"
    return "opencode"  # Default to opencode


def create_chat_ui():
    graph = StateGraph(State)

    opencode_app = create_opencode_graph()
    research_app = create_research_graph()

    def run_opencode(state):
        result = opencode_app.invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    def run_research(state):
        result = research_app.invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    graph.add_node("opencode", run_opencode)
    graph.add_node("research", run_research)

    graph.add_conditional_edges(START, router, ["opencode", "research", END])
    graph.add_edge("opencode", END)
    graph.add_edge("research", END)

    return graph.compile()


def chat():
    """Interactive chat loop with dark mode UI"""
    app = create_chat_ui()
    messages = []
    
    DARK_MODE = {
        "header": "\033[1;36m",
        "user": "\033[1;32m",
        "assistant": "\033[1;33m",
        "error": "\033[1;31m",
        "reset": "\033[0m",
        "dim": "\033[2m"
    }
    
    print(f"{DARK_MODE['header']}{'=' * 70}{DARK_MODE['reset']}")
    print(f"{DARK_MODE['header']}  LangGraph Agent Chat UI - Dark Mode{DARK_MODE['reset']}")
    print(f"{DARK_MODE['header']}{'=' * 70}{DARK_MODE['reset']}")
    print(f"{DARK_MODE['dim']}  Agents: OpenCode (coding) | Research (web scraping){DARK_MODE['reset']}")
    print(f"{DARK_MODE['dim']}  Type 'quit' to exit | 'clear' to clear history{DARK_MODE['reset']}")
    print(f"{DARK_MODE['header']}{'=' * 70}{DARK_MODE['reset']}\n")
    
    while True:
        try:
            user_input = input(f"{DARK_MODE['user']}You:{DARK_MODE['reset']} ").strip()
        except EOFError:
            break
            
        if user_input.lower() in ["quit", "exit"]:
            print(f"{DARK_MODE['dim']}Goodbye!{DARK_MODE['reset']}")
            break
        
        if user_input.lower() == "clear":
            messages = []
            print(f"{DARK_MODE['dim']}Chat history cleared.{DARK_MODE['reset']}\n")
            continue
        
        if not user_input:
            continue
        
        messages.append({"role": "user", "content": user_input})
        result = app.invoke({"messages": messages})
        
        assistant_msg = result["messages"][-1]["content"]
        print(f"\n{DARK_MODE['assistant']}Agent:{DARK_MODE['reset']} {assistant_msg}\n")
        messages.append({"role": "assistant", "content": assistant_msg})


if __name__ == "__main__":
    chat()
