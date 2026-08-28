from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from langchain_core.messages import AIMessage
from temporalio.client import WorkflowFailureError
from temporalio.common import RetryPolicy
from temporalio.exceptions import CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from src import coding_agent
from src.coder_temporal_client import start_or_attach_coder_workflow
from src.coder_temporal_worker import (
    CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    create_coder_temporal_interceptors,
    create_coder_temporal_plugin,
)
from src.coder_temporal_workflow import CoderTemporalRequest, CoderTemporalWorkflow
from src.coding_persistence import coding_session_id


def _request(operation_id: str, workspace: str, content: str = "Do the work"):
    return CoderTemporalRequest(
        operation_id=operation_id,
        messages=[{"role": "user", "content": content}],
        workspace=workspace,
        model=None,
        execution_mode="read_only",
        user_identity="temporal-user",
    )


@pytest.mark.asyncio
async def test_temporal_execution_replay_restart_and_stable_identity(
    monkeypatch, tmp_path
):
    runs = []

    class App:
        async def ainvoke(self, payload, config=None):
            del config
            content = payload["messages"][-1]["content"]
            runs.append(content)
            if content == "Fail safely":
                raise RuntimeError("provider-secret-detail")
            return {
                "messages": [*payload["messages"], AIMessage(content="Coder result")],
                "todos": [],
            }

    async def session_agent(*_args):
        return App()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)
    request = _request("coder-operation-1", str(tmp_path))
    second_request = _request("coder-operation-2", str(tmp_path), "Second operation")
    failure_request = _request("coder-operation-3", str(tmp_path), "Fail safely")
    task_queue = "coder-temporal-integration"

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        first_plugin = create_coder_temporal_plugin()
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            plugins=[first_plugin],
            interceptors=create_coder_temporal_interceptors(),
        ):
            handle = await start_or_attach_coder_workflow(
                environment.client,
                request,
                task_queue=task_queue,
            )
            result = await handle.result()
            history = await handle.fetch_history()

        second_plugin = create_coder_temporal_plugin()
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            plugins=[second_plugin],
            interceptors=create_coder_temporal_interceptors(),
        ):
            attached = await start_or_attach_coder_workflow(
                environment.client,
                request,
                task_queue=task_queue,
            )
            attached_result = await attached.result()
            second = await start_or_attach_coder_workflow(
                environment.client,
                second_request,
                task_queue=task_queue,
            )
            second_result = await second.result()
            failure = await start_or_attach_coder_workflow(
                environment.client,
                failure_request,
                task_queue=task_queue,
            )
            failure_result = await failure.result()

        await Replayer(
            workflows=[CoderTemporalWorkflow],
            plugins=[create_coder_temporal_plugin()],
        ).replay_workflow(history)

    assert result.operation_id == request.operation_id
    assert result.coding_status == "completed"
    assert result.messages[-1]["content"].startswith("Completion report")
    assert result.coding_session_id == coding_session_id(
        thread_identity=request.operation_id,
        workspace=tmp_path,
        user_identity=request.user_identity,
    )
    assert attached_result == result
    assert second_result.operation_id == second_request.operation_id
    assert second_result.coding_session_id != result.coding_session_id
    assert failure_result.coding_status == "error"
    assert "agent_failure" in failure_result.messages[-1]["content"]
    assert "provider-secret-detail" not in failure_result.messages[-1]["content"]
    assert runs == ["Do the work", "Second operation", "Fail safely"]

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
    assert scheduled[0].retry_policy.maximum_attempts == 1


@pytest.mark.asyncio
async def test_temporal_cancellation_reaches_running_coder_activity(
    monkeypatch, tmp_path
):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class App:
        async def ainvoke(self, payload, config=None):
            del payload, config
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    async def session_agent(*_args):
        return App()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)
    request = _request("coder-cancel-operation", str(tmp_path))
    task_queue = "coder-temporal-cancellation"

    async with (
        await WorkflowEnvironment.start_time_skipping() as environment,
        Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            plugins=[
                create_coder_temporal_plugin(
                    heartbeat_timeout=timedelta(milliseconds=200)
                )
            ],
            interceptors=create_coder_temporal_interceptors(),
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


@pytest.mark.asyncio
async def test_temporal_timeout_does_not_retry_side_effecting_coder(
    monkeypatch, tmp_path
):
    runs = 0
    release = asyncio.Event()

    class App:
        async def ainvoke(self, payload, config=None):
            nonlocal runs
            del payload, config
            runs += 1
            await release.wait()

    async def session_agent(*_args):
        return App()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: False)
    request = _request("coder-timeout-operation", str(tmp_path))
    task_queue = "coder-temporal-timeout"
    plugin = create_coder_temporal_plugin(
        start_to_close_timeout=timedelta(milliseconds=100),
        heartbeat_timeout=timedelta(milliseconds=50),
        retry_policy=RetryPolicy(maximum_attempts=1),
    )

    async with (
        await WorkflowEnvironment.start_time_skipping() as environment,
        Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[CoderTemporalWorkflow],
            plugins=[plugin],
            interceptors=create_coder_temporal_interceptors(),
        ),
    ):
        handle = await start_or_attach_coder_workflow(
            environment.client,
            request,
            task_queue=task_queue,
        )
        with pytest.raises(WorkflowFailureError):
            await handle.result()
        release.set()

    assert runs == 1
