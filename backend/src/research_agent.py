import operator
from pathlib import Path
from typing import Annotated, TypedDict

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.graph import DeepAgentState
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from src.agent_utils import get_conversation_history
from src.llm import get_agent_llm
from src.research_evidence import (
    ingest_uploaded_sources,
    read_saved_source,
    read_workspace_source,
    research_read_url,
    research_web_search,
)

load_dotenv()


class State(TypedDict, total=False):
    messages: Annotated[list, operator.add]
    research_findings: str
    model: str
    workspace: str
    thread_identity: str
    user_identity: str
    session_evidence: Annotated[list[dict], operator.add]


class ResearchState(DeepAgentState, total=False):
    workspace: str
    thread_identity: str
    user_identity: str
    session_evidence: Annotated[list[dict], operator.add]


RESEARCH_PROMPT = """You are Research, Jasper's evidence specialist.

Use web_search for current or externally verifiable claims and read_url only for
pages you explicitly choose to visit. Search results are snippet-only evidence;
never describe them as read pages. Use ingest_uploaded_sources for files explicitly
uploaded by the user. Use read_workspace_source for a safe text file inside the
selected workspace, and read_saved_source to reuse session evidence without another
web request. You may list, glob, and grep the selected workspace to discover files,
but you cannot write files or execute commands.

Preserve every evidence ID in the final findings. State limitations and uncertainty
plainly. Never invent a source, crawl a site, or claim to have read unavailable
content. Return concise findings for Jasper, not internal tool history."""


def _workspace_backend(workspace: str | None):
    root = Path(workspace or Path(__file__).resolve().parents[2]).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace must be a directory")
    backend = FilesystemBackend(root_dir=root, virtual_mode=True)
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=[
                "/.env",
                "/.env.*",
                "/**/.env",
                "/**/.env.*",
                "/.git",
                "/.git/**",
                "/**/.git",
                "/**/.git/**",
                "/**/*.key",
                "/**/*.pem",
                "/**/*.p12",
                "/**/*.pfx",
            ],
            mode="deny",
        ),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    return backend, permissions


def create_research_agent(model=None, *, workspace: str | None = None, store=None):
    """Build Research with documented Deep Agents read-only filesystem access."""

    backend, permissions = _workspace_backend(workspace)
    return create_deep_agent(
        model=model or get_agent_llm(),
        tools=[
            research_web_search,
            research_read_url,
            ingest_uploaded_sources,
            read_workspace_source,
            read_saved_source,
        ],
        system_prompt=RESEARCH_PROMPT,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=["read_file", "ls", "glob", "grep"],
            )
        ],
        backend=backend,
        permissions=permissions,
        state_schema=ResearchState,
        store=store,
        name="research",
    )


async def research_agent(state: State, runtime: Runtime | None = None):
    """Run Research as a visible top-level specialist and return only its findings."""

    try:
        result = await create_research_agent(
            get_agent_llm(state.get("model")),
            workspace=state.get("workspace"),
            store=runtime.store if runtime is not None else None,
        ).ainvoke(
            {
                "messages": get_conversation_history(state["messages"]),
                "workspace": state.get("workspace", ""),
                "thread_identity": state.get("thread_identity", ""),
                "user_identity": state.get("user_identity", "anonymous"),
                "session_evidence": state.get("session_evidence", []),
            }
        )
        response = next(
            message
            for message in reversed(result["messages"])
            if isinstance(message, AIMessage) and not message.tool_calls
        )
        return {
            "messages": [
                AIMessage(
                    content=response.content,
                    additional_kwargs={"speaker_profile": "research"},
                )
            ],
            "research_findings": response.content,
            "session_evidence": result.get("session_evidence", []),
        }
    except Exception:
        error_msg = (
            "[Research Agent]\n\nThe research provider is currently unavailable."
        )
        return {
            "messages": [
                AIMessage(
                    content=error_msg, additional_kwargs={"speaker_profile": "research"}
                )
            ],
            "research_findings": error_msg,
        }


def create_research_graph():
    graph = StateGraph(State)
    graph.add_node("research_agent", research_agent)
    graph.add_edge(START, "research_agent")
    graph.add_edge("research_agent", END)
    return graph.compile()
