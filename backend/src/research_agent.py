from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, List
import operator
import os
from src.agent_utils import get_user_query, get_conversation_history
from src.llm import get_llm
from dotenv import load_dotenv

load_dotenv()


class State(TypedDict):
    messages: Annotated[List[dict], operator.add]
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
        response = llm.invoke(
            [{"role": "system", "content": system_prompt}]
            + history
        )
        return {"messages": [{"role": "assistant", "content": response.content}], "research_findings": response.content}
    except Exception as e:
        error_msg = f"""[Research Agent]

Error: {str(e)}

Make sure the OpenCode bridge proxy is running:
```bash
cd ~/fun-multi-character-chats/opencode-bridge && ./start_proxy.sh
```"""
        return {"messages": [{"role": "assistant", "content": error_msg}], "research_findings": error_msg}


def create_research_graph():
    graph = StateGraph(State)
    graph.add_node("research_agent", research_agent)
    graph.add_edge(START, "research_agent")
    graph.add_edge("research_agent", END)
    return graph.compile()


if __name__ == "__main__":
    app = create_research_graph()
    result = app.invoke({"messages": [{"role": "user", "content": "Research LangGraph best practices"}]})
    print(result["research_findings"])
