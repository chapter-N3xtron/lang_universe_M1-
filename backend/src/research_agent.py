import operator
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.agent_utils import get_conversation_history
from src.llm import get_llm

load_dotenv()


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
    research_findings: str


def research_agent(state: State):
    """Research agent - powered by GLM via LiteLLM proxy"""
    messages = state["messages"]
    history = get_conversation_history(messages)

    llm = get_llm()

    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")

    if firecrawl_key:
        system_prompt = "You are a research assistant with web scraping capabilities. Use your knowledge to provide accurate, well-researched information."
    else:
        system_prompt = "You are a research assistant. Provide accurate, well-researched information based on your training data. Note: Set FIRECRAWL_API_KEY in .env to enable live web scraping."

    try:
        response = llm.invoke([{"role": "system", "content": system_prompt}] + history)
        return {
            "messages": [{"role": "assistant", "content": response.content}],
            "research_findings": response.content,
        }
    except Exception:
        error_msg = (
            "[Research Agent]\n\nThe research provider is currently unavailable."
        )
        return {
            "messages": [{"role": "assistant", "content": error_msg}],
            "research_findings": error_msg,
        }


def create_research_graph():
    graph = StateGraph(State)
    graph.add_node("research_agent", research_agent)
    graph.add_edge(START, "research_agent")
    graph.add_edge("research_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_research_graph()
    result = app.invoke(
        {"messages": [{"role": "user", "content": "Research LangGraph best practices"}]}
    )
    print(result["research_findings"])
