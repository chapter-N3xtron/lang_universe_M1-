"""Temporal activity that invokes Agent Server without owning inner graph state."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from typing import Any

from langgraph_sdk import get_client
from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.coder_temporal_contract import (
    CODER_AGENT_SERVER_ACTIVITY_NAME,
    CODER_AGENT_SERVER_GRAPH_ID,
    CoderTemporalRequest,
    CoderTemporalResult,
)


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


def _operation_key(operation_id: str) -> str:
    return hashlib.sha256(operation_id.encode()).hexdigest()


async def _join_existing_operation(client, request: CoderTemporalRequest):
    operation_key = _operation_key(request.operation_id)
    for run in await client.runs.list(request.thread_id, limit=100):
        if not isinstance(run, Mapping):
            continue
        metadata = run.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        if metadata.get("operation_key") != operation_key:
            continue
        if run.get("status") not in {"pending", "running", "success", "interrupted"}:
            return None
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return None
        return await client.runs.join(request.thread_id, run_id)
    return None


@activity.defn(name=CODER_AGENT_SERVER_ACTIVITY_NAME)
async def invoke_agent_server_coder(
    request: CoderTemporalRequest,
) -> CoderTemporalResult:
    client = get_client(
        url=os.getenv("AGENT_SERVER_URL", "http://127.0.0.1:8123").rstrip("/")
    )
    result = await _join_existing_operation(client, request)
    if result is None:
        result = await client.runs.wait(
            request.thread_id,
            CODER_AGENT_SERVER_GRAPH_ID,
            input={
                "messages": request.messages,
                "workspace": request.workspace,
                "model": request.model,
                "execution_mode": request.execution_mode,
                "thread_identity": request.thread_id,
                "user_identity": request.user_identity,
            },
            metadata={
                "operation_id": request.operation_id[:128],
                "operation_key": _operation_key(request.operation_id),
                "temporal_workflow_id": activity.info().workflow_id[:128],
                "authority_source": "agent_server_postgresql",
            },
            multitask_strategy="reject",
            durability="sync",
        )
    if not isinstance(result, dict):
        raise ApplicationError(
            "Agent Server returned an invalid Coder result",
            type="InvalidCoderResult",
            non_retryable=True,
        )
    status = result.get("coding_status")
    if status not in {"completed", "blocked", "error"}:
        if result.get("__interrupt__"):
            status = "blocked"
        else:
            raise ApplicationError(
                "Agent Server returned an invalid Coder terminal status",
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
        thread_id=request.thread_id,
        messages=messages,
        workspace=str(result.get("workspace") or request.workspace),
        execution_manifest=safe_manifest,
        coding_status=status,
        ui=ui,
    )
