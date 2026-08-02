import operator
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.graph import END, START, StateGraph

from src.agent_utils import get_conversation_history
from src.jasper_tools import read_url, web_search
from src.llm import get_agent_llm

load_dotenv()


class State(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]
    research_findings: str
    model: str


RESEARCH_PROMPT = """You are Research, Jasper's web-research specialist.

Use web_search for current or externally verifiable claims. Use read_url when the
full content of an authoritative result is needed. If a page cannot be read, use the
available search evidence or another authoritative result rather than repeatedly
requesting the same unavailable page. Preserve the evidence IDs returned by tools in
your findings so Jasper can cite them in a grounded visualization. State limitations
and uncertainty plainly. Never invent a source or claim to have read a page that a
tool could not retrieve."""


def create_research_agent(model=None):
    """Build the documented LangChain subagent used for web research."""

    return create_agent(
        model=model or get_agent_llm(),
        tools=[web_search, read_url],
        system_prompt=RESEARCH_PROMPT,
        name="research",
    )


def research_agent(state: State):
    """Run Research as a standalone profile in the outer LangGraph."""
    messages = state["messages"]
    history = get_conversation_history(messages)

    try:
        result = create_research_agent(
            get_agent_llm(state.get("model"))
        ).invoke({"messages": history})
        response = result["messages"][-1]
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
