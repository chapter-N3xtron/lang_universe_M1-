"""Provider-neutral Deep Agents coding subgraph."""

from __future__ import annotations

import asyncio
import logging
import operator
import os
from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.ui import (
    AnyUIMessage,
    delete_ui_message,
    push_ui_message,
    ui_message_reducer,
)

from src.coding_persistence import coding_session_id, export_coding_session
from src.llm import get_coding_llm
from src.macos_host_operations import (
    create_request_macos_host_operation_tool,
    load_operator_config,
)
from src.workspace_policy import (
    ExecutionManifest,
    WorkspacePolicyError,
    canonical_workspace,
    execution_manifest,
    format_execution_manifest,
)

InvalidWorkspaceError = WorkspacePolicyError


class CodingAgentState(TypedDict, total=False):
    messages: Annotated[list[Any], operator.add]
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: str
    execution_manifest: ExecutionManifest
    ui: Annotated[list[AnyUIMessage], ui_message_reducer]


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
logger = logging.getLogger(__name__)

_SESSION_AGENT_CACHE: OrderedDict[tuple[str, str, str, str], Any] = OrderedDict()
_SESSION_AGENT_CACHE_SIZE = 8
_CODING_TOOL_PATHS = ("/opt/coding-tools/node/bin", "/opt/coding-tools/pnpm")
_CODING_PROGRESS_INTERVAL_SECONDS = 15 * 60

_HOST_OPERATION_INTERRUPT = {
    "allowed_decisions": ["approve", "reject"],
    "description": (
        "Review this exact macOS host-operation plan. Approval only resumes receipt "
        "verification; host execution is independently confirmed outside Coding."
    ),
}
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
    """Compatibility wrapper around the shared fail-closed workspace policy."""

    return canonical_workspace(raw_workspace)


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


def _deep_agent_components():
    # Lazy imports let the rollback backend and unit tests start without loading
    # the comparatively large Deep Agents dependency tree.
    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import FilesystemBackend, LocalShellBackend

    return FilesystemPermission, FilesystemBackend, LocalShellBackend, create_deep_agent


def _execution_mode(raw_mode: str | None) -> str:
    if raw_mode in {"approval", "autonomous"}:
        return raw_mode
    return "read_only"


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
    mode = _execution_mode(execution_mode)
    approval_mode = mode == "approval"
    autonomous_mode = mode == "autonomous"
    permissions = [
        permission_type(
            operations=["read", "write"],
            paths=_SENSITIVE_VIRTUAL_PATHS,
            mode="deny",
        ),
    ]
    permissions.extend(
        [
            permission_type(operations=["read"], paths=["/**"], mode="allow"),
            permission_type(
                operations=["write"],
                paths=["/**"],
                mode="allow" if approval_mode or autonomous_mode else "deny",
            ),
        ]
    )
    if approval_mode or autonomous_mode:
        backend = local_shell_backend_type(
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
    else:
        backend = filesystem_backend_type(root_dir=workspace, virtual_mode=True)
    operator_config = load_operator_config()
    mutable_mode = approval_mode or autonomous_mode
    host_tool_enabled = operator_config is not None and mutable_mode
    tools = []
    if host_tool_enabled and operator_config is not None:
        tools.append(create_request_macos_host_operation_tool(operator_config))
    broker_interrupts = (
        {"request_macos_host_operation": _HOST_OPERATION_INTERRUPT}
        if host_tool_enabled
        else {}
    )
    if approval_mode:
        interrupt_on = {**_LOCAL_APPROVAL_INTERRUPT_ON, **broker_interrupts}
    elif autonomous_mode and broker_interrupts:
        interrupt_on = broker_interrupts
    else:
        interrupt_on = None
    if approval_mode:
        mutation_prompt = (
            "Use the built-in repository file tools and execute tool for coding work. "
            "Every write, edit, deletion, or shell command pauses for human review. "
            "Commands start in the selected repository. Never read or modify secrets "
            "or edit .git files directly. Use normal Git commands for repository "
            "management; never force-push or delete remote history."
        )
    elif autonomous_mode:
        mutation_prompt = (
            "Work autonomously in the selected repository using the native Deep Agents "
            "filesystem and shell tools. Follow repository instructions and validate "
            "your work with the available project commands. Never read or modify secrets "
            "or edit .git files directly."
        )
    else:
        mutation_prompt = (
            "This deployment is read-only: never write, edit, delete, or execute files."
        )
    memory = ["/AGENTS.md"] if (workspace / "AGENTS.md").is_file() else None
    skills = (
        ["/.agents/skills/"] if (workspace / ".agents" / "skills").is_dir() else None
    )
    manifest_text = format_execution_manifest(execution_manifest(workspace))

    return create_deep_agent(
        model=get_coding_llm(model_name),
        tools=tools,
        name="coding_agent",
        system_prompt=(
            "You are the repository coding agent. The exact selected repository is "
            "authoritative, including when it is empty. Never search parent, child, "
            "or sibling directories for another repository; never substitute the "
            "home directory, current working directory, /workspace, or another "
            "checkout. Use absolute virtual paths rooted at /, which maps only to "
            "the selected repository. The shell is container-only. For every Docker "
            "or Docker Compose task, use request_macos_host_operation with exactly one "
            "typed docker_sandbox action only when the execution manifest reports that "
            "capability available; if it is unavailable, report that exact blocker. "
            "Bind each request to the current Compose file with its SHA-256 digest. "
            "For every docker_sandbox action, set action.workspace exactly to the "
            f"server-produced selected repository host path {workspace}; never use a "
            "virtual path such as /local-deployment-sandbox as action.workspace. "
            "Set action.project_directory relative to that workspace and set "
            "action.compose_file relative to the project directory. For example, virtual "
            "/local-deployment-sandbox/compose.yaml means project_directory "
            "local-deployment-sandbox and compose_file compose.yaml. For pull, build, up, "
            "start, stop, restart, or down, expected_mutations must contain exactly one "
            "replace mutation whose path exactly equals action.workspace; rollback.strategy "
            "must be none and rollback.may_require_human_inspection must be true. For ps, "
            "declare one inspect mutation at action.workspace, use rollback.strategy none, "
            "and do not claim a mutation. "
            "Never request Docker inspection, logs, exec, raw commands, names, argv, "
            "environment, or secrets. Issue one Docker sandbox host-operation request "
            "alone per assistant turn, with no other tool calls in that turn, and wait "
            "for its complete native confirmation and signed receipt before another. "
            "Commands execute in the Linux Agent Server container; repository files "
            "originate from the macOS-host bind mount. Never describe container "
            "commands as Mac-host commands or infer a macOS mutation from Linux "
            "output. For work requiring macOS, a native "
            "application, Homebrew, DMG handling, or /Applications, call "
            "request_macos_host_operation only when the execution manifest reports "
            "that capability available; otherwise report the host operation as "
            "unavailable and do not attempt a Linux substitute. Issue exactly one "
            "request_macos_host_operation call in an assistant turn, with no other "
            "tool calls in that turn. Never batch Mac-host inspections or mutations; "
            "wait for the complete review and receipt cycle before requesting another. "
            "For multi-step work, create and maintain a task list with write_todos before "
            "implementation. If the request names an OpenSpec change, use only its relevant "
            "tasks; otherwise turn the request into a short checklist. Keep working until "
            "every requested task is complete or genuinely blocked, and continue independent "
            "tasks when one task is blocked. The live 15-minute report is generated from this "
            "task list, so update it after each task. Record a genuine blocker as a pending "
            "task beginning with 'BLOCKER: ' so the report can show it. End with a Completion "
            "report in simple "
            "plain English. Give every task a short note, expand each abbreviation on first "
            "use, explain code examples for people who do not read code easily, state what "
            "the code does, identify the simplest solution, and clearly identify material "
            "risks without pressuring the human.\n\n"
            + manifest_text
            + "\n\n"
            + mutation_prompt
        ),
        memory=memory,
        skills=skills,
        backend=backend,
        permissions=None if approval_mode or autonomous_mode else permissions,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )


async def _session_agent(
    workspace: Path,
    model_name: str | None,
    execution_mode: str,
):
    mode = _execution_mode(execution_mode)
    operator_config = load_operator_config()
    host_config_identity = (
        f"{operator_config.endpoint}:{operator_config.key_id}"
        if operator_config is not None
        else "unavailable"
    )
    key = (str(workspace), model_name or "", mode, host_config_identity)
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


def _report_tasks(raw_todos: Any) -> list[dict[str, str]]:
    if not isinstance(raw_todos, list):
        return []
    notes = {
        "completed": "Completed during this run.",
        "in_progress": "Coder is working on this now.",
        "pending": "Not started yet.",
    }
    tasks: list[dict[str, str]] = []
    for raw_todo in raw_todos[:100]:
        if not isinstance(raw_todo, dict):
            continue
        content = raw_todo.get("content")
        status = raw_todo.get("status")
        if not isinstance(content, str) or status not in notes:
            continue
        content = content.strip()
        if not content:
            continue
        tasks.append(
            {
                "task": content[:500],
                "status": status,
                "note": notes[status],
            }
        )
    return tasks


def _progress_report_props(raw_todos: Any, report_number: int) -> dict[str, Any]:
    tasks = _report_tasks(raw_todos)
    if not tasks:
        tasks = [
            {
                "task": "Requested coding work",
                "status": "in_progress",
                "note": "Coder has not published a detailed task list yet.",
            }
        ]
    blockers = [
        task["task"].split(":", 1)[1].strip()
        for task in tasks
        if task["status"] != "completed"
        and task["task"].upper().startswith("BLOCKER: ")
    ]
    return {
        "report_number": report_number,
        "elapsed_minutes": report_number * 15,
        "tasks": tasks,
        "blockers": blockers,
    }


def _has_incomplete_tasks(raw_todos: Any) -> bool:
    tasks = _report_tasks(raw_todos)
    return bool(tasks) and any(task["status"] != "completed" for task in tasks)


def _completion_report_text(content: str, raw_todos: Any) -> str:
    if content.lstrip().lower().startswith("completion report"):
        return content
    tasks = _report_tasks(raw_todos)
    lines = ["Completion report", "", "Tasks"]
    if tasks:
        for task in tasks:
            status = "Completed" if task["status"] == "completed" else "Not completed"
            task_text = task["task"].rstrip(".!?")
            lines.append(f"- {status}: {task_text}. Note: {task['note']}")
    else:
        lines.append(
            "- Finished: Requested coding work. Note: See Coder notes below for the outcome."
        )
    lines.extend(["", "Coder notes", content])
    return "\n".join(lines)


def _format_completion_report(messages: list[Any], raw_todos: Any) -> list[Any]:
    formatted = list(messages)
    for index in range(len(formatted) - 1, -1, -1):
        message = formatted[index]
        if _message_type(message) not in {"ai", "assistant"} or _tool_calls(message):
            continue
        content = _message_text(message)
        if not content:
            continue
        report = _completion_report_text(content, raw_todos)
        if isinstance(message, dict):
            replacement = dict(message)
            replacement["content"] = report
        else:
            replacement = message.model_copy(update={"content": report})
        formatted[index] = replacement
        break
    return formatted


def _failure_report(error_code: str) -> str:
    return (
        "Completion report\n\n"
        "Tasks\n"
        "- Not completed: Requested coding work. "
        f"Note: Coder stopped because of {error_code}.\n\n"
        "Blocker\n"
        "The task needs attention before work can continue."
    )


def _format_coding_result(
    messages: list[Any], manifest: ExecutionManifest
) -> list[Any]:
    """Attach the same deterministic execution identity to the final result."""

    formatted = list(messages)
    for index in range(len(formatted) - 1, -1, -1):
        message = formatted[index]
        if _message_type(message) not in {"ai", "assistant"} or _tool_calls(message):
            continue
        content = _message_text(message)
        if not content:
            continue
        result_text = f"{content}\n\n{format_execution_manifest(manifest)}"
        if isinstance(message, dict):
            replacement = dict(message)
            replacement["content"] = result_text
            replacement["execution_manifest"] = dict(manifest)
        else:
            additional_kwargs = dict(getattr(message, "additional_kwargs", {}))
            additional_kwargs["execution_manifest"] = dict(manifest)
            replacement = message.model_copy(
                update={
                    "content": result_text,
                    "additional_kwargs": additional_kwargs,
                }
            )
        formatted[index] = replacement
        break
    return formatted


async def _invoke_session(
    app: Any,
    input_messages: list[Any],
    config: RunnableConfig,
) -> dict[str, Any]:
    return await _stream_session(app, {"messages": input_messages}, config)


async def _stream_session(
    app: Any,
    payload: Any,
    config: RunnableConfig,
    report_interval_seconds: float = _CODING_PROGRESS_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Stream standard LangGraph values and let interrupts propagate."""
    if not hasattr(app, "astream"):
        return await app.ainvoke(payload, config=config)
    if report_interval_seconds <= 0:
        raise ValueError("report interval must be positive")

    latest_values: dict[str, Any] = {}
    stream = app.astream(payload, config=config, stream_mode="values").__aiter__()
    next_values = asyncio.create_task(anext(stream))
    loop = asyncio.get_running_loop()
    next_report_at = loop.time() + report_interval_seconds
    report_number = 0
    report_id: str | None = None
    completed_normally = False
    try:
        while True:
            wait_seconds = max(0.0, next_report_at - loop.time())
            done, _pending = await asyncio.wait({next_values}, timeout=wait_seconds)
            if next_values in done:
                try:
                    values = next_values.result()
                except StopAsyncIteration:
                    completed_normally = True
                    break
                if isinstance(values, dict):
                    latest_values = values
                next_values = asyncio.create_task(anext(stream))
                continue

            report_number += 1
            try:
                event = push_ui_message(
                    "coder_progress_report",
                    _progress_report_props(latest_values.get("todos"), report_number),
                    id=report_id,
                    state_key="ui",
                )
                report_id = event["id"]
            except RuntimeError:
                logger.warning("Coder progress report could not be published")
            next_report_at += report_interval_seconds
            while next_report_at <= loop.time():
                next_report_at += report_interval_seconds
    finally:
        if not next_values.done():
            next_values.cancel()
            await asyncio.gather(next_values, return_exceptions=True)

    if completed_normally and report_id is not None:
        try:
            delete_ui_message(report_id, state_key="ui")
        except RuntimeError:
            logger.warning("Coder progress report could not be cleared")
    return latest_values


async def deep_agents_coding_node(
    state: CodingAgentState, config: RunnableConfig = None
) -> dict[str, Any]:
    session_id = ""
    manifest: ExecutionManifest | None = None
    workspace: Path | None = None
    try:
        workspace = _validated_workspace(state.get("workspace"))
        manifest = execution_manifest(workspace)
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
        app = await _session_agent(
            workspace,
            state.get("model"),
            execution_mode,
        )
        result = await _invoke_session(app, input_messages, config or {})
        all_messages = result.get("messages", [])
        raw_todos = result.get("todos", [])
        new_messages = _current_turn_output(all_messages)
        if not _has_final_assistant_message(new_messages):
            error_messages = [
                AIMessage(content=_failure_report("missing_final_result"))
            ]
            return {
                "messages": _format_coding_result(error_messages, manifest),
                "workspace": str(workspace),
                "execution_manifest": manifest,
                "coding_session_id": session_id,
                "coding_status": "error",
            }
        completion_messages = _format_completion_report(new_messages, raw_todos)
        return {
            "messages": _format_coding_result(completion_messages, manifest),
            "workspace": str(workspace),
            "execution_manifest": manifest,
            "coding_session_id": session_id,
            "coding_status": (
                "blocked" if _has_incomplete_tasks(raw_todos) else "completed"
            ),
        }
    except asyncio.CancelledError:
        raise
    except GraphBubbleUp:
        raise
    except InvalidWorkspaceError:
        error_code = "invalid_workspace"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "coding_session_id": session_id},
        )
    except ImportError:
        error_code = "dependency_unavailable"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "coding_session_id": session_id},
        )
    except Exception:
        error_code = "agent_failure"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "coding_session_id": session_id},
        )

    error_messages = [AIMessage(content=_failure_report(error_code))]
    if manifest is not None:
        error_messages = _format_coding_result(error_messages, manifest)
    response: dict[str, Any] = {
        "messages": error_messages,
        "coding_session_id": session_id,
        "coding_status": "error",
    }
    if workspace is not None and manifest is not None:
        response.update(
            {
                "workspace": str(workspace),
                "execution_manifest": manifest,
            }
        )
    return response


def create_coding_agent_graph():
    graph = StateGraph(CodingAgentState)
    graph.add_node("coding_agent", deep_agents_coding_node)
    graph.add_edge(START, "coding_agent")
    graph.add_edge("coding_agent", END)
    return graph.compile()
