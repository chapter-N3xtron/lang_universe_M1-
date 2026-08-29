"""Provider-neutral Deep Agents coding subgraph."""

from __future__ import annotations

import asyncio
import logging
import operator
import os
from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Any, Literal, TypeAlias

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.ui import (
    AnyUIMessage,
    delete_ui_message,
    push_ui_message,
    ui_message_reducer,
)
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from src.custodian_backend import CustodianBackend, CustodianClient, CustodianError
from src.llm import get_coding_llm
from src.phase5_tools import CODER_PHASE5_TOOLS
from src.runtime_authority import RuntimeIdentityError, authoritative_thread_id
from src.workspace_policy import (
    ExecutionManifest,
    WorkspacePolicyError,
    canonical_workspace,
    execution_manifest,
    format_execution_manifest,
)

InvalidWorkspaceError = WorkspacePolicyError


CoderMessages: TypeAlias = Annotated[list[Any], operator.add]
CoderUIEvents: TypeAlias = Annotated[list[AnyUIMessage], ui_message_reducer]
CoderStatus: TypeAlias = Literal["completed", "blocked", "error"]


class CoderInputState(TypedDict, total=False):
    messages: CoderMessages
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str


class CoderOutputState(TypedDict, total=False):
    messages: CoderMessages
    workspace: str
    execution_manifest: ExecutionManifest
    coding_session_id: str
    coding_status: CoderStatus
    ui: CoderUIEvents


class CoderState(TypedDict, total=False):
    messages: CoderMessages
    workspace: str
    model: str | None
    execution_mode: str
    thread_identity: str
    user_identity: str
    coding_session_id: str
    coding_status: CoderStatus
    execution_manifest: ExecutionManifest
    ui: CoderUIEvents


CodingAgentState = CoderState


logger = logging.getLogger(__name__)

_SESSION_AGENT_CACHE: OrderedDict[tuple[str, str, str, str], Any] = OrderedDict()
_SESSION_AGENT_CACHE_SIZE = 8
_CODING_PROGRESS_INTERVAL_SECONDS = 15 * 60
_HOST_WORKER_URL = os.getenv(
    "CUSTODIAN_WORKER_URL", "http://host.docker.internal:8765"
).rstrip("/")


class ComposeTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    compose_files: list[str] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Repository-relative Compose file paths. Omit this field to use the "
            "repository's default Compose file."
        ),
    )
    arguments: list[str] = Field(
        default_factory=list,
        max_length=128,
        description=(
            "Options and service names that follow the Compose subcommand. Do not include "
            "docker, compose, --file, or the subcommand here."
        ),
    )
    timeout: int = Field(default=60, ge=1, le=300)


class ComposeReadTask(ComposeTask):
    subcommand: Literal["config", "logs", "ps"] = Field(
        description="The read-only Docker Compose subcommand to execute."
    )


class ComposeChangeTask(ComposeTask):
    subcommand: Literal["build", "pull", "start", "stop", "restart", "up", "down"] = (
        Field(description="The Docker Compose deployment subcommand to execute.")
    )


class ComposeEnvironmentTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    compose_file: str = Field(
        min_length=1,
        max_length=4096,
        description=(
            "Repository-relative Docker Compose file whose explicitly required local "
            "variables Custodian should generate beside it."
        ),
    )


class GitHubPublishTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    repository_name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$",
    )
    description: str = Field(default="", max_length=350)


def create_custodian_boundary_tools(workspace: Path) -> list[StructuredTool]:
    client = CustodianClient(str(workspace), base_url=_HOST_WORKER_URL, timeout=305)

    def invoke(action: str, argv: list[str], timeout: int = 60) -> str:
        try:
            result = client.action(action, argv=argv, timeout=timeout)
        except CustodianError:
            return "Custodian command request failed."
        output = str(result.get("output") or result.get("error") or "")
        return (
            f"exit_code={result.get('exit_code')} truncated={bool(result.get('truncated'))}\n"
            f"{output}"
        )

    def invoke_compose(
        action: str,
        subcommand: str,
        compose_files: list[str] | None = None,
        arguments: list[str] | None = None,
        timeout: int = 60,
    ) -> str:
        argv = [
            item
            for compose_file in (compose_files or [])
            for item in ("--file", compose_file)
        ]
        argv.extend([subcommand, *(arguments or [])])
        return invoke(action, argv, timeout)

    def prepare_compose_environment(compose_file: str) -> str:
        try:
            result = client.action(
                "compose_prepare_environment", compose_file=compose_file
            )
        except CustodianError:
            return "Custodian Compose environment preparation failed."
        if result.get("ok") is not True:
            return str(result.get("error") or "Compose environment preparation failed.")
        return (
            "Custodian prepared the broker-held Compose environment with "
            f"{int(result.get('generated') or 0)} newly generated value(s). "
            "No credential values were returned to the coding agent."
        )

    def publish(repository_name: str, description: str = "") -> str:
        try:
            result = client.action(
                "github_publish",
                repository_name=repository_name,
                description=description,
            )
        except CustodianError:
            return "Custodian GitHub publication request failed."
        if result.get("ok") is not True:
            return str(result.get("error") or "GitHub publication failed.")
        return (
            f"Published private repository {result['owner']}/{result['repository']} "
            f"from branch {result['branch']} and set it as origin: "
            f"{result['repository_url']}"
        )

    return [
        StructuredTool.from_function(
            func=prepare_compose_environment,
            name="custodian_compose_prepare_environment",
            description=(
                "Generate any explicitly required local Docker Compose variables through "
                "Custodian and write them to an ignored .env file beside the selected Compose "
                "file. Values remain broker-held and are never returned to the coding agent. "
                "Use this when Compose reports missing local environment values; do not ask the "
                "human to create or reveal them."
            ),
            args_schema=ComposeEnvironmentTask,
        ),
        StructuredTool.from_function(
            func=lambda subcommand, compose_files=None, arguments=None, timeout=60: (
                invoke_compose(
                    "compose_read",
                    subcommand,
                    compose_files,
                    arguments,
                    timeout,
                )
            ),
            name="custodian_compose_read",
            description=(
                "Inspect Docker Compose state in the selected repository. Select config, logs, "
                "or ps as subcommand; provide Compose files and trailing arguments in their "
                "separate typed fields."
            ),
            args_schema=ComposeReadTask,
        ),
        StructuredTool.from_function(
            func=lambda subcommand, compose_files=None, arguments=None, timeout=60: (
                invoke_compose(
                    "compose_change",
                    subcommand,
                    compose_files,
                    arguments,
                    timeout,
                )
            ),
            name="custodian_compose_change",
            description=(
                "Run a Docker Compose deployment change requested by the human. Select build, "
                "pull, start, stop, restart, up, or down as subcommand; provide Compose files "
                "and trailing options or service names in their separate typed fields. The "
                "explicit task request authorizes the requested sequence without a second "
                "per-command interruption."
            ),
            args_schema=ComposeChangeTask,
        ),
        StructuredTool.from_function(
            func=publish,
            name="custodian_github_publish",
            description=(
                "After the human explicitly requests external publication, create one private "
                "repository in the fixed chapter-N3xtron GitHub account, push the selected "
                "repository's committed current branch, and set the new repository as origin. "
                "Tracked changes must already be committed. GitHub credentials remain with "
                "Custodian and are never available to the coding agent."
            ),
            args_schema=GitHubPublishTask,
        ),
    ]


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
        "description": "Review a native Custodian shell command in the selected repository.",
    },
    "custodian_compose_read": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a read-only Docker Compose inspection.",
    },
    "custodian_github_publish": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": (
            "Approve or reject creating a private chapter-N3xtron repository, pushing "
            "the selected branch, and replacing origin."
        ),
    },
}

_AUTONOMOUS_BOUNDARY_INTERRUPT_ON = {
    "custodian_github_publish": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": (
            "Approve or reject creating a private chapter-N3xtron repository, pushing "
            "the selected branch, and replacing origin."
        ),
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
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware

    return TodoListMiddleware, create_deep_agent


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
    todo_middleware_type, create_deep_agent = _deep_agent_components()
    mode = _execution_mode(execution_mode)
    approval_mode = mode == "approval"
    autonomous_mode = mode == "autonomous"
    mutable_mode = approval_mode or autonomous_mode
    backend = CustodianBackend(str(workspace), read_only=not mutable_mode)
    # Keep every existing Custodian boundary tool and add only delegated Store tools.
    tools = list(create_custodian_boundary_tools(workspace) if mutable_mode else [])
    tools.extend(CODER_PHASE5_TOOLS)
    interrupt_on = (
        _LOCAL_APPROVAL_INTERRUPT_ON
        if approval_mode
        else _AUTONOMOUS_BOUNDARY_INTERRUPT_ON
        if autonomous_mode
        else None
    )
    if approval_mode:
        mutation_prompt = (
            "Use the built-in repository file tools and the built-in execute tool. "
            "Repository writes, edits, deletions, and execute calls pause for human review. "
            "Commands run through native Custodian and start in the selected repository. "
            "Never read or modify secrets or edit .git files directly. Use normal Git commands "
            "for repository management; commit only when the human explicitly requests it. "
            "Remote Git operations are unavailable."
        )
    elif autonomous_mode:
        mutation_prompt = (
            "Work autonomously in the selected repository using the native Custodian filesystem "
            "backend and built-in execute tool. Follow repository instructions and validate your "
            "work with normal shell commands. Never read or modify secrets or edit .git files "
            "directly. Commit only when the human explicitly requests it; remote Git operations "
            "are unavailable."
        )
    else:
        mutation_prompt = (
            "This deployment is read-only: never write, edit, delete, or execute files."
        )
    # Host paths intentionally do not exist in the Agent Server container. The
    # Custodian backend discovers repository instructions through normal reads.
    memory = None
    skills = None
    manifest_text = format_execution_manifest(execution_manifest(workspace))

    return create_deep_agent(
        model=get_coding_llm(model_name),
        tools=tools,
        name="coding_agent",
        system_prompt=(
            "You are the repository coding agent. The exact selected repository is authoritative, "
            "including when it is empty. Never search parent, child, or sibling directories for "
            "another repository or substitute another checkout. The built-in filesystem uses "
            "absolute virtual paths rooted at /, which maps only to the selected repository. "
            "Native Custodian is the sole filesystem and command boundary. Use the built-in "
            "execute tool for normal shell, Git, build, test, package, and host commands; it runs "
            "on macOS from the selected repository, not inside the Agent Server container. When "
            "the current explicit human task requires work elsewhere on the host, use execute with "
            "that absolute path instead of claiming the host path is unavailable. The human's "
            "explicit task authorizes required command sequences, including requested "
            "builds and service restarts, subject to Custodian's credential, destructive-command, "
            "repository, and timeout protections. Use custodian_compose_prepare_environment when "
            "required local Compose values are missing, then use custodian_compose_read or "
            "custodian_compose_change so broker-held values never enter the agent environment. "
            "Never ask the human to provide those local values. Use custodian_github_publish only "
            "after the human explicitly requests a new private repository in chapter-N3xtron; it "
            "publishes the committed current branch and replaces origin after explicit approval. "
            "Do not request executor, broker, docker_sandbox, or request_macos_host_operation "
            "interfaces; they are obsolete and must never be reported as blockers. "
            f"Repository operations remain bound to the exact host repository {workspace}. "
            "For multi-step work, create and maintain a task list with write_todos before "
            "implementation. The human's current explicit request authorizes all requested "
            "implementation and host work. Treat OpenSpec artifacts as planning context, not as "
            "a second authorization gate: proceed even when an OpenSpec change is incomplete, "
            "planning-only, or defers that work to a later change. Do not require another "
            "OpenSpec change or approval before acting. Use execute for ordinary command work and "
            "reserve typed Custodian tools for their broker-only Compose and publication boundaries. "
            "Otherwise turn the request into a short checklist. Keep working until "
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
        middleware=[todo_middleware_type()],
        backend=backend,
        permissions=None,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )


async def _session_agent(
    workspace: Path,
    model_name: str | None,
    execution_mode: str,
):
    mode = _execution_mode(execution_mode)
    key = (str(workspace), model_name or "", mode, _HOST_WORKER_URL)
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
    state: CoderState, config: RunnableConfig = None
) -> CoderOutputState:
    session_id = ""
    manifest: ExecutionManifest | None = None
    workspace: Path | None = None
    try:
        thread_identity = authoritative_thread_id(
            state.get("thread_identity"),
            config,
            operation="coder_graph_run",
        )
        session_id = thread_identity
        workspace = _validated_workspace(state.get("workspace"))
        manifest = execution_manifest(workspace)
        execution_mode = _execution_mode(state.get("execution_mode"))
        input_messages = list(state.get("messages", []))
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
    except (asyncio.CancelledError, GraphBubbleUp, RuntimeIdentityError):
        raise
    except InvalidWorkspaceError:
        error_code = "invalid_workspace"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "thread_id": session_id},
        )
    except ImportError:
        error_code = "dependency_unavailable"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "thread_id": session_id},
        )
    except Exception:
        error_code = "agent_failure"
        logger.exception(
            "Coding agent failed",
            extra={"coding_error_code": error_code, "thread_id": session_id},
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


def create_coding_agent_graph_builder():
    graph = StateGraph(
        CoderState,
        input_schema=CoderInputState,
        output_schema=CoderOutputState,
    )
    graph.add_node("coding_agent", deep_agents_coding_node)
    graph.add_edge(START, "coding_agent")
    graph.add_edge("coding_agent", END)
    return graph


def create_coding_agent_graph():
    return create_coding_agent_graph_builder().compile()
