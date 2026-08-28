"""Temporal workflow for outer Agent Server Coder orchestration."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from src.coder_temporal_contract import (
    CODER_AGENT_SERVER_ACTIVITY_NAME,
    CoderTemporalRequest,
    CoderTemporalResult,
)

CODER_TEMPORAL_WORKFLOW_NAME = "coder"
CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT = timedelta(hours=24)
CODER_ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(seconds=10)
CODER_ACTIVITY_RETRY_POLICY = RetryPolicy(maximum_attempts=3)


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
    if not request.thread_id.strip():
        raise ApplicationError(
            "thread_id is required",
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
        return await workflow.execute_activity(
            CODER_AGENT_SERVER_ACTIVITY_NAME,
            request,
            result_type=CoderTemporalResult,
            start_to_close_timeout=CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=CODER_ACTIVITY_RETRY_POLICY,
        )


__all__ = [
    "CoderTemporalRequest",
    "CoderTemporalResult",
    "CoderTemporalWorkflow",
]
