from __future__ import annotations

import asyncio

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner, Worker

from src.coder_temporal_client import start_or_attach_coder_workflow
from src.coder_temporal_contract import CODER_AGENT_SERVER_ACTIVITY_NAME
from src.coder_temporal_worker import (
    CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    CODER_ACTIVITY_RETRY_POLICY,
    CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    create_coder_temporal_interceptors,
)
from src.coder_temporal_workflow import (
    CoderTemporalRequest,
    CoderTemporalResult,
    CoderTemporalWorkflow,
)


def _request(operation_id: str, workspace: str, content: str = "Do the work"):
    return CoderTemporalRequest(
        operation_id=operation_id,
        thread_id="agent-server-thread-stable",
        messages=[{"role": "user", "content": content}],
        workspace=workspace,
        model=None,
        execution_mode="read_only",
        user_identity="temporal-user",
    )


def _result(request: CoderTemporalRequest) -> CoderTemporalResult:
    return CoderTemporalResult(
        operation_id=request.operation_id,
        thread_id=request.thread_id,
        messages=[{"type": "ai", "content": "Coder result"}],
        workspace=request.workspace,
        execution_manifest={"selected_repository": request.workspace},
        coding_status="completed",
        ui=[],
    )


@pytest.mark.asyncio
async def test_temporal_replay_restart_and_retry_preserve_agent_server_thread(tmp_path):
    attempts: list[tuple[str, str]] = []

    @activity.defn(name=CODER_AGENT_SERVER_ACTIVITY_NAME)
    async def invoke(request: CoderTemporalRequest) -> CoderTemporalResult:
        attempts.append((request.operation_id, request.thread_id))
        if len(attempts) == 1:
            raise RuntimeError("transient outer invocation failure")
        return _result(request)

    request = _request("coder-operation-1", str(tmp_path))
    task_queue = "coder-temporal-integration"

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            activities=[invoke],
            interceptors=create_coder_temporal_interceptors(),
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            handle = await start_or_attach_coder_workflow(
                environment.client,
                request,
                task_queue=task_queue,
            )
            result = await handle.result()
            history = await handle.fetch_history()

        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            activities=[invoke],
            interceptors=create_coder_temporal_interceptors(),
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            attached = await start_or_attach_coder_workflow(
                environment.client,
                request,
                task_queue=task_queue,
            )
            attached_result = await attached.result()

        await Replayer(
            workflows=[CoderTemporalWorkflow],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ).replay_workflow(history)

    assert result == attached_result == _result(request)
    assert attempts == [
        (request.operation_id, request.thread_id),
        (request.operation_id, request.thread_id),
    ]
    scheduled = [
        event.activity_task_scheduled_event_attributes
        for event in history.events
        if event.HasField("activity_task_scheduled_event_attributes")
    ]
    assert len(scheduled) == 1
    assert scheduled[0].start_to_close_timeout.ToTimedelta() == (
        CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT
    )
    assert scheduled[0].heartbeat_timeout.ToTimedelta() == (
        CODER_ACTIVITY_HEARTBEAT_TIMEOUT
    )
    assert (
        scheduled[0].retry_policy.maximum_attempts
        == CODER_ACTIVITY_RETRY_POLICY.maximum_attempts
    )


@pytest.mark.asyncio
async def test_temporal_cancellation_reaches_outer_agent_server_activity(tmp_path):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    @activity.defn(name=CODER_AGENT_SERVER_ACTIVITY_NAME)
    async def invoke(request: CoderTemporalRequest) -> CoderTemporalResult:
        del request
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    request = _request("coder-cancel-operation", str(tmp_path))
    task_queue = "coder-temporal-cancellation"

    async with (
        await WorkflowEnvironment.start_time_skipping() as environment,
        Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            activities=[invoke],
            interceptors=create_coder_temporal_interceptors(),
            workflow_runner=UnsandboxedWorkflowRunner(),
        ),
    ):
        handle = await start_or_attach_coder_workflow(
            environment.client,
            request,
            task_queue=task_queue,
        )
        await asyncio.wait_for(started.wait(), timeout=10)
        await handle.cancel()
        with pytest.raises(WorkflowFailureError) as failure:
            await handle.result()
        await asyncio.wait_for(cancelled.wait(), timeout=10)

    assert isinstance(failure.value.__cause__, CancelledError)
