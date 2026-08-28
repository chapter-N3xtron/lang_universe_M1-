"""Internal Temporal client helpers for idempotent Coder startup."""

from __future__ import annotations

from temporalio.client import Client, WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.coder_temporal_workflow import (
    CoderTemporalRequest,
    CoderTemporalResult,
    CoderTemporalWorkflow,
)


async def start_or_attach_coder_workflow(
    client: Client,
    request: CoderTemporalRequest,
    *,
    task_queue: str,
) -> WorkflowHandle[CoderTemporalWorkflow, CoderTemporalResult]:
    try:
        return await client.start_workflow(
            CoderTemporalWorkflow.run,
            request,
            id=request.operation_id,
            task_queue=task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        return client.get_workflow_handle_for(
            CoderTemporalWorkflow.run,
            request.operation_id,
        )
