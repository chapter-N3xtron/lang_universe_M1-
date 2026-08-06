"""Provider-neutral Deep Agents coding subgraph."""

from __future__ import annotations

import asyncio
import operator
import os
from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph

from src.coding_events import CodingEventEmitter
from src.coding_persistence import coding_session_id, export_coding_session
from src.llm import get_coding_llm


class CodingAgentState(TypedDict, total=False):
    messages: Annotated[list[Any], operator.add]
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    coding_events: list[dict[str, Any]]


class InvalidWorkspaceError(ValueError):
    """Raised when a coding request is not confined to an absolute directory."""


_SENSITIVE_VIRTUAL_PATHS = [
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
]
_SESSION_AGENT_CACHE: OrderedDict[tuple[str, str, str], Any] = OrderedDict()
_SESSION_AGENT_CACHE_SIZE = 8
_CODING_TOOL_PATHS = ("/opt/coding-tools/node/bin", "/opt/coding-tools/pnpm")

_LOCAL_APPROVAL_INTERRUPT_ON = {
    "write_file": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a file write in the selected repository.",
    },
    "edit_file": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a file edit in the selected repository.",
    },
    "delete": {
        "allowed_decisions": ["approve", "reject"],
        "description": "Review a file deletion in the selected repository.",
    },
    "execute": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a shell command rooted in the selected repository.",
    },
}


def _validated_workspace(raw_workspace: str | None) -> Path:
    if not raw_workspace:
        raise InvalidWorkspaceError("workspace is required")
    candidate = Path(raw_workspace).expanduser()
    if not candidate.is_absolute():
        raise InvalidWorkspaceError("workspace must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise InvalidWorkspaceError("workspace does not exist") from exc
    if not resolved.is_dir():
        raise InvalidWorkspaceError("workspace must be a directory")
    return resolved


def _event_writer():
    try:
        return get_stream_writer()
    except RuntimeError:
        return lambda _event: None


def _message_type(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "type", ""))


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    if isinstance(message, dict):
        calls = message.get("tool_calls", [])
    else:
        calls = getattr(message, "tool_calls", [])
    return calls if isinstance(calls, list) else []


def _coding_events(messages: list[Any]) -> list[dict[str, Any]]:
    """Create bounded, provider-neutral event summaries from agent messages."""
    events: list[dict[str, Any]] = []
    for message in messages:
        for call in _tool_calls(message):
            events.append(
                {
                    "type": "tool_call",
                    "name": str(call.get("name", "unknown")),
                    "id": str(call.get("id", "")),
                }
            )
        if isinstance(message, ToolMessage) or _message_type(message) == "tool":
            tool_call_id = (
                message.get("tool_call_id", "")
                if isinstance(message, dict)
                else getattr(message, "tool_call_id", "")
            )
            events.append({"type": "tool_result", "id": str(tool_call_id)})
    return events


def _export_message(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return {
            "type": message.get("type") or message.get("role") or "unknown",
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
        }
    return {
        "type": getattr(message, "type", type(message).__name__),
        "content": getattr(message, "content", ""),
        "tool_calls": getattr(message, "tool_calls", []),
    }


def _deep_agent_components():
    # Lazy imports let the rollback backend and unit tests start without loading
    # the comparatively large Deep Agents dependency tree.
    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend, LocalShellBackend

    return FilesystemPermission, FilesystemBackend, LocalShellBackend, create_deep_agent


def _execution_mode(raw_mode: str | None) -> str:
    return "approval" if raw_mode == "approval" else "read_only"


def _build_deep_agent(
    workspace: Path,
    model_name: str | None,
    execution_mode: str = "read_only",
    checkpointer: Any = None,
):
    (
        permission_type,
        filesystem_backend_type,
        local_shell_backend_type,
        create_deep_agent,
    ) = _deep_agent_components()
    approval_mode = _execution_mode(execution_mode) == "approval"
    permissions = [
        permission_type(
            operations=["read", "write"],
            paths=_SENSITIVE_VIRTUAL_PATHS,
            mode="deny",
        ),
        permission_type(operations=["read"], paths=["/**"], mode="allow"),
        permission_type(
            operations=["write"],
            paths=["/**"],
            mode="allow" if approval_mode else "deny",
        ),
    ]
    backend = (
        local_shell_backend_type(
            root_dir=workspace,
            virtual_mode=True,
            timeout=120,
            max_output_bytes=100_000,
            env={
                "PATH": os.pathsep.join(
                    (*_CODING_TOOL_PATHS, os.environ.get("PATH", ""))
                ),
                "NPM_CONFIG_PREFIX": "/opt/coding-tools/node",
                "PNPM_HOME": "/opt/coding-tools/pnpm",
            },
            inherit_env=True,
        )
        if approval_mode
        else filesystem_backend_type(root_dir=workspace, virtual_mode=True)
    )
    interrupt_on = _LOCAL_APPROVAL_INTERRUPT_ON if approval_mode else None
    mutation_prompt = (
        "Use the built-in repository file tools and execute tool for coding work. "
        "Every write, edit, deletion, or shell command pauses for human review. "
        "Commands start in the selected repository. Never read or modify secrets "
        "or edit .git files directly. Use normal Git commands for repository "
        "management; never force-push or delete remote history."
        if approval_mode
        else "This deployment is read-only: never write, edit, delete, or execute files."
    )
    memory = ["/AGENTS.md"] if (workspace / "AGENTS.md").is_file() else None
    skills = (
        ["/.agents/skills/"] if (workspace / ".agents" / "skills").is_dir() else None
    )

    return create_deep_agent(
        model=get_coding_llm(model_name),
        tools=[],
        name="coding_agent",
        system_prompt=(
            "You are the repository coding agent. Inspect only the selected "
            "workspace. Use absolute virtual paths rooted at /. " + mutation_prompt
        ),
        memory=memory,
        skills=skills,
        backend=backend,
        permissions=None if approval_mode else permissions,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )


async def _session_agent(workspace: Path, model_name: str | None, execution_mode: str):
    mode = _execution_mode(execution_mode)
    key = (str(workspace), model_name or "", mode)
    if key in _SESSION_AGENT_CACHE:
        app = _SESSION_AGENT_CACHE.pop(key)
        _SESSION_AGENT_CACHE[key] = app
        return app
    app = _build_deep_agent(
        workspace,
        model_name,
        execution_mode=mode,
        checkpointer=None,
    )
    _SESSION_AGENT_CACHE[key] = app
    while len(_SESSION_AGENT_CACHE) > _SESSION_AGENT_CACHE_SIZE:
        _SESSION_AGENT_CACHE.popitem(last=False)
    return app


async def export_coding_session_state(
    *,
    thread_identity: str,
    workspace: Path,
    user_identity: str = "anonymous",
    model_name: str | None = None,
) -> dict[str, Any]:
    del model_name
    workspace = _validated_workspace(str(workspace))
    session_id = coding_session_id(
        thread_identity=thread_identity,
        workspace=workspace,
        user_identity=user_identity,
    )
    return await export_coding_session(session_id)


def _current_turn_output(messages: list[Any]) -> list[Any]:
    for index in range(len(messages) - 1, -1, -1):
        if _message_type(messages[index]) in {"human", "user"}:
            return messages[index + 1 :]
    return messages


def _message_text(message: Any) -> str:
    content = (
        message.get("content", "")
        if isinstance(message, dict)
        else getattr(message, "content", "")
    )
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ).strip()
    return ""


def _has_final_assistant_message(messages: list[Any]) -> bool:
    return any(
        _message_type(message) in {"ai", "assistant"}
        and not _tool_calls(message)
        and bool(_message_text(message))
        for message in reversed(messages)
    )


async def _invoke_session(
    app: Any,
    input_messages: list[Any],
    config: RunnableConfig,
    *,
    emitter: CodingEventEmitter,
) -> dict[str, Any]:
    return await _stream_session(
        app, {"messages": input_messages}, config, emitter
    )


async def _stream_session(
    app: Any,
    payload: Any,
    config: RunnableConfig,
    emitter: CodingEventEmitter,
) -> dict[str, Any]:
    """Stream the native nested graph and let its interrupts propagate."""
    if not hasattr(app, "astream"):
        return await app.ainvoke(payload, config=config)

    async for event in app.astream(
        payload,
        config=config,
        stream_mode=["messages", "updates", "values"],
        subgraphs=True,
    ):
        emitter.consume(event)
    return dict(emitter.latest_values)


async def deep_agents_coding_node(
    state: CodingAgentState, config: RunnableConfig = None
) -> dict[str, Any]:
    writer = _event_writer()
    session_id = ""
    error_type = None
    emitter = CodingEventEmitter(writer, session_id)
    try:
        workspace = _validated_workspace(state.get("workspace"))
        execution_mode = _execution_mode(state.get("execution_mode"))
        input_messages = list(state.get("messages", []))
        thread_identity = str(state.get("thread_identity") or "")
        if not thread_identity:
            raise InvalidWorkspaceError("thread identity is required")
        session_id = coding_session_id(
            thread_identity=thread_identity,
            workspace=workspace,
            user_identity=str(state.get("user_identity") or "anonymous"),
        )
        emitter = CodingEventEmitter(writer, session_id)
        emitter.emit("status", "running")
        app = await _session_agent(workspace, state.get("model"), execution_mode)
        invocation = _invoke_session(
            app,
            input_messages,
            config or {},
            emitter=emitter,
        )
        timeout_seconds = int(os.getenv("CODING_AGENT_TIMEOUT_SECONDS", "240"))
        result = await asyncio.wait_for(invocation, timeout=timeout_seconds)
        all_messages = result.get("messages", [])
        new_messages = _current_turn_output(all_messages)
        emitter.flush_text()
        for event in _coding_events(new_messages):
            emitter.tool(
                event.get("name", "tool"),
                event.get("id", ""),
                "completed" if event["type"] == "tool_result" else "running",
            )
        if not _has_final_assistant_message(new_messages):
            emitter.emit("error", "error", code="missing_final_result")
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The coding agent did not return a final result "
                            "(missing_final_result)."
                        )
                    )
                ],
                "coding_session_id": session_id,
                "coding_status": "error",
                "coding_events": emitter.events,
            }
        emitter.emit("status", "completed")
        return {
            "messages": new_messages,
            "coding_session_id": session_id,
            "coding_status": "completed",
            "coding_events": emitter.events,
        }
    except asyncio.CancelledError:
        emitter.flush_text()
        emitter.emit("status", "cancelled")
        raise
    except GraphBubbleUp:
        raise
    except InvalidWorkspaceError:
        error_code = "invalid_workspace"
    except ImportError:
        error_code = "dependency_unavailable"
    except TimeoutError:
        error_code = "agent_timeout"
    except Exception as exc:
        error_code = "agent_failure"
        error_type = type(exc).__name__

    emitter.flush_text()
    error_data = {"code": error_code}
    if error_type:
        error_data["exception_type"] = error_type
    emitter.emit("error", "error", **error_data)
    return {
        "messages": [
            AIMessage(
                content=(
                    f"The coding agent could not complete this request ({error_code})."
                )
            )
        ],
        "coding_session_id": session_id,
        "coding_status": "error",
        "coding_events": emitter.events,
    }


def create_coding_agent_graph():
    graph = StateGraph(CodingAgentState)
    graph.add_node("coding_agent", deep_agents_coding_node)
    graph.add_edge(START, "coding_agent")
    graph.add_edge("coding_agent", END)
    return graph.compile()
