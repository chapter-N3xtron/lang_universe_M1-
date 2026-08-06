from langchain_core.runnables import RunnableConfig
from open_deep_research.deep_researcher import deep_researcher

from src.agent_utils import get_conversation_history


async def librarian_agent(state: dict, config: RunnableConfig) -> dict:
    messages = get_conversation_history(state.get("messages", []))
    result = await deep_researcher.ainvoke({"messages": messages}, config=config)
    return {"messages": result.get("messages", [])[len(messages) :]}
