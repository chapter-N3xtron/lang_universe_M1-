from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.graph import StateGraph
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.converter import DataConverter
from temporalio.exceptions import WorkflowAlreadyStartedError

from src import coder_agent_server_activity, coding_agent
from src.coder_agent_server_activity import invoke_agent_server_coder
from src.coder_temporal_client import start_or_attach_coder_workflow
from src.coder_temporal_heartbeat import CoderActivityHeartbeatInterceptor
from src.coder_temporal_worker import (
    CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    CODER_ACTIVITY_RETRY_POLICY,
    CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    create_coder_temporal_interceptors,
)
from src.coder_temporal_workflow import CoderTemporalRequest, CoderTemporalResult


def _request(operation_id: str = "coder-operation-1") -> CoderTemporalRequest:
    return CoderTemporalRequest(
        operation_id=operation_id,
        thread_id="agent-server-thread-1",
        messages=[{"role": "user", "content": "Do the work"}],
        workspace="/tmp/coder-workspace",
        model=None,
        execution_mode="read_only",
        user_identity="user-1",
    )


def test_standalone_coder_is_persistence_neutral_and_agent_server_registered():
    builder = coding_agent.create_coding_agent_graph_builder()
    compiled = coding_agent.create_coding_agent_graph()
    backend = Path(coding_agent.__file__).parent.parent
    langgraph = json.loads((backend / "langgraph.json").read_text())

    assert isinstance(builder, StateGraph)
    assert builder.state_schema is coding_agent.CoderState
    assert builder.input_schema is coding_agent.CoderInputState
    assert builder.output_schema is coding_agent.CoderOutputState
    assert set(builder.nodes) == {"coding_agent"}
    assert builder.nodes["coding_agent"].metadata is None
    assert compiled.checkpointer is None
    assert compiled.store is None
    assert langgraph["graphs"] == {
        "chat_ui": "./src/chat_ui.py:create_chat_ui",
        "coder": "./src/coding_agent.py:create_coding_agent_graph",
    }


def test_temporal_worker_uses_outer_activity_without_langgraph_plugin():
    interceptors = create_coder_temporal_interceptors()

    assert len(interceptors) == 1
    assert isinstance(interceptors[0], CoderActivityHeartbeatInterceptor)
    assert CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT.total_seconds() > 0
    assert CODER_ACTIVITY_HEARTBEAT_TIMEOUT.total_seconds() > 0
    assert CODER_ACTIVITY_RETRY_POLICY.maximum_attempts == 3

    backend = Path(coding_agent.__file__).parent
    temporal_sources = "\n".join(
        path.read_text() for path in backend.glob("coder_temporal*.py")
    )
    worker_source = (backend / "coder_temporal_worker.py").read_text()
    assert "LangGraphPlugin" not in temporal_sources
    assert "create_coding_agent_graph" not in temporal_sources
    assert "activities=[invoke_agent_server_coder]" in worker_source


@pytest.mark.asyncio
async def test_temporal_contract_round_trips_through_supported_converter():
    request = _request()
    result = CoderTemporalResult(
        operation_id=request.operation_id,
        thread_id=request.thread_id,
        messages=[{"type": "ai", "content": "Completed"}],
        workspace=request.workspace,
        execution_manifest={
            "filesystem_origin": "native_custodian",
            "selected_repository": request.workspace,
            "command_runtime": "native_custodian_host",
            "host_worker": "unavailable",
        },
        coding_status="completed",
        ui=[],
    )
    converter = DataConverter.default

    payloads = await converter.encode([request, result])
    decoded = await converter.decode(
        payloads,
        [CoderTemporalRequest, CoderTemporalResult],
    )

    assert decoded == [request, result]


@pytest.mark.asyncio
async def test_outer_activity_preserves_thread_and_uses_agent_server_authority(
    monkeypatch,
):
    request = _request()

    class Runs:
        def __init__(self):
            self.call = None

        async def list(self, thread_id, *, limit):
            assert thread_id == request.thread_id
            assert limit == 100
            return []

        async def wait(self, thread_id, graph_id, **kwargs):
            self.call = (thread_id, graph_id, kwargs)
            return {
                "messages": [{"role": "assistant", "content": "Completed"}],
                "workspace": request.workspace,
                "execution_manifest": {"selected_repository": request.workspace},
                "coding_status": "completed",
                "ui": [],
            }

    runs = Runs()
    monkeypatch.setattr(
        coder_agent_server_activity,
        "get_client",
        lambda **_kwargs: SimpleNamespace(runs=runs),
    )
    monkeypatch.setattr(
        coder_agent_server_activity.activity,
        "info",
        lambda: SimpleNamespace(workflow_id=request.operation_id),
    )

    result = await invoke_agent_server_coder(request)

    thread_id, graph_id, kwargs = runs.call
    assert thread_id == request.thread_id
    assert graph_id == "coder"
    assert kwargs["input"]["thread_identity"] == request.thread_id
    assert kwargs["metadata"]["operation_id"] == request.operation_id
    assert kwargs["metadata"]["operation_key"] == (
        coder_agent_server_activity._operation_key(request.operation_id)
    )
    assert kwargs["metadata"]["authority_source"] == "agent_server_postgresql"
    assert kwargs["multitask_strategy"] == "reject"
    assert kwargs["durability"] == "sync"
    assert result.thread_id == request.thread_id
    assert result.coding_status == "completed"


@pytest.mark.asyncio
async def test_outer_activity_retry_joins_existing_agent_server_run(monkeypatch):
    request = _request()

    class Runs:
        def __init__(self):
            self.join_call = None

        async def list(self, thread_id, *, limit):
            assert thread_id == request.thread_id
            assert limit == 100
            return [
                {
                    "run_id": "existing-run",
                    "status": "success",
                    "metadata": {
                        "operation_key": coder_agent_server_activity._operation_key(
                            request.operation_id
                        )
                    },
                }
            ]

        async def join(self, thread_id, run_id):
            self.join_call = (thread_id, run_id)
            return {
                "messages": [{"role": "assistant", "content": "Completed"}],
                "workspace": request.workspace,
                "execution_manifest": {"selected_repository": request.workspace},
                "coding_status": "completed",
                "ui": [],
            }

        async def wait(self, *_args, **_kwargs):
            raise AssertionError("retry must not start duplicate inner work")

    runs = Runs()
    monkeypatch.setattr(
        coder_agent_server_activity,
        "get_client",
        lambda **_kwargs: SimpleNamespace(runs=runs),
    )

    result = await invoke_agent_server_coder(request)

    assert runs.join_call == (request.thread_id, "existing-run")
    assert result.thread_id == request.thread_id
    assert result.coding_status == "completed"


@pytest.mark.asyncio
async def test_start_uses_operation_id_and_idempotent_temporal_policies():
    expected_handle = object()

    class Client:
        def __init__(self):
            self.call = None

        async def start_workflow(self, workflow, request, **kwargs):
            self.call = (workflow, request, kwargs)
            return expected_handle

    client = Client()
    request = _request()

    handle = await start_or_attach_coder_workflow(
        client,
        request,
        task_queue="coder-queue",
    )

    assert handle is expected_handle
    _, passed_request, kwargs = client.call
    assert passed_request is request
    assert kwargs["id"] == request.operation_id
    assert kwargs["task_queue"] == "coder-queue"
    assert kwargs["id_conflict_policy"] is WorkflowIDConflictPolicy.USE_EXISTING
    assert kwargs["id_reuse_policy"] is WorkflowIDReusePolicy.REJECT_DUPLICATE


@pytest.mark.asyncio
async def test_closed_duplicate_attaches_without_starting_unrelated_work():
    expected_handle = object()

    class Client:
        async def start_workflow(self, *_args, **_kwargs):
            raise WorkflowAlreadyStartedError("coder-operation-1", "coder")

        def get_workflow_handle_for(self, workflow, workflow_id):
            self.attachment = (workflow, workflow_id)
            return expected_handle

    client = Client()
    request = _request()

    handle = await start_or_attach_coder_workflow(
        client,
        request,
        task_queue="coder-queue",
    )

    assert handle is expected_handle
    assert client.attachment[1] == request.operation_id
