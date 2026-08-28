"""Temporal Workflow contract for the authoritative Coder graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from temporalio import workflow
from temporalio.contrib.langgraph import graph
from temporalio.exceptions import ApplicationError

CODER_TEMPORAL_GRAPH_NAME = "coder"
CODER_TEMPORAL_WORKFLOW_NAME = "coder"
CoderTemporalStatus = Literal["completed", "blocked", "error"]


@dataclass(frozen=True)
class CoderTemporalRequest:
    operation_id: str
    messages: list[dict[str, Any]]
    workspace: str
    model: str | None
    execution_mode: str
    user_identity: str


@dataclass(frozen=True)
class CoderTemporalResult:
    operation_id: str
    messages: list[dict[str, str]]
    workspace: str
    execution_manifest: dict[str, str]
    coding_session_id: str
    coding_status: CoderTemporalStatus
    ui: list[dict[str, Any]]


def _message_result(message: Any) -> dict[str, str] | None:
    if isinstance(message, dict):
        message_type = message.get("type") or message.get("role") or "unknown"
        content = message.get("content", "")
    else:
        message_type = getattr(message, "type", "unknown")
        content = getattr(message, "content", "")
    if not isinstance(content, str):
        if isinstance(content, list):
            content = "\n".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
        else:
            content = ""
    if not content:
        return None
    return {"type": str(message_type), "content": content}


def _validate_request(request: CoderTemporalRequest) -> None:
    if not request.operation_id.strip():
        raise ApplicationError(
            "operation_id is required",
            type="InvalidCoderRequest",
            non_retryable=True,
        )
    if request.operation_id != workflow.info().workflow_id:
        raise ApplicationError(
            "operation_id must match the Temporal Workflow ID",
            type="InvalidCoderRequest",
            non_retryable=True,
        )
    if not request.workspace.strip():
        raise ApplicationError(
            "workspace is required",
            type="InvalidCoderRequest",
            non_retryable=True,
        )
    if request.execution_mode not in {"approval", "autonomous", "read_only"}:
        raise ApplicationError(
            "execution_mode must be approval, autonomous, or read_only",
            type="InvalidCoderRequest",
            non_retryable=True,
        )
    if not request.user_identity.strip():
        raise ApplicationError(
            "user_identity is required",
            type="InvalidCoderRequest",
            non_retryable=True,
        )
    if not request.messages:
        raise ApplicationError(
            "messages are required",
            type="InvalidCoderRequest",
            non_retryable=True,
        )


@workflow.defn(name=CODER_TEMPORAL_WORKFLOW_NAME)
class CoderTemporalWorkflow:
    @workflow.run
    async def run(self, request: CoderTemporalRequest) -> CoderTemporalResult:
        _validate_request(request)
        coder = graph(CODER_TEMPORAL_GRAPH_NAME).compile()
        result = await coder.ainvoke(
            {
                "messages": request.messages,
                "workspace": request.workspace,
                "model": request.model,
                "execution_mode": request.execution_mode,
                "thread_identity": request.operation_id,
                "user_identity": request.user_identity,
            }
        )
        status = result.get("coding_status")
        if status not in {"completed", "blocked", "error"}:
            raise ApplicationError(
                "Coder returned an invalid terminal status",
                type="InvalidCoderResult",
                non_retryable=True,
            )
        messages = [
            sanitized
            for message in result.get("messages", [])
            if (sanitized := _message_result(message)) is not None
        ]
        manifest = result.get("execution_manifest")
        safe_manifest = (
            {str(key): str(value) for key, value in manifest.items()}
            if isinstance(manifest, dict)
            else {}
        )
        ui = [dict(event) for event in result.get("ui", []) if isinstance(event, dict)]
        return CoderTemporalResult(
            operation_id=request.operation_id,
            messages=messages,
            workspace=str(result.get("workspace") or request.workspace),
            execution_manifest=safe_manifest,
            coding_session_id=str(result.get("coding_session_id") or ""),
            coding_status=status,
            ui=ui,
        )
