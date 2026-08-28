from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.graph import StateGraph
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.contrib.langgraph import LangGraphPlugin
from temporalio.converter import DataConverter
from temporalio.exceptions import WorkflowAlreadyStartedError

from src import coding_agent
from src.coder_temporal_client import start_or_attach_coder_workflow
from src.coder_temporal_heartbeat import CoderActivityHeartbeatInterceptor
from src.coder_temporal_worker import (
    CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    CODER_ACTIVITY_RETRY_POLICY,
    CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    create_coder_temporal_interceptors,
    create_coder_temporal_plugin,
)
from src.coder_temporal_workflow import CoderTemporalRequest, CoderTemporalResult


def _request(operation_id: str = "coder-operation-1") -> CoderTemporalRequest:
    return CoderTemporalRequest(
        operation_id=operation_id,
        messages=[{"role": "user", "content": "Do the work"}],
        workspace="/tmp/coder-workspace",
        model=None,
        execution_mode="read_only",
        user_identity="user-1",
    )


def test_authoritative_builder_serves_supervisor_and_temporal_plugin():
    builder = coding_agent.create_coding_agent_graph_builder()
    compiled = coding_agent.create_coding_agent_graph()

    assert isinstance(builder, StateGraph)
    assert builder.state_schema is coding_agent.CoderState
    assert builder.input_schema is coding_agent.CoderInputState
    assert builder.output_schema is coding_agent.CoderOutputState
    assert set(builder.nodes) == {"coding_agent"}
    assert builder.nodes["coding_agent"].metadata == {"execute_in": "activity"}
    assert compiled.builder.state_schema is builder.state_schema
    assert compiled.builder.input_schema is builder.input_schema
    assert compiled.builder.output_schema is builder.output_schema
    assert set(compiled.get_graph().nodes) == {"__start__", "coding_agent", "__end__"}

    plugin = create_coder_temporal_plugin()
    interceptors = create_coder_temporal_interceptors()

    assert isinstance(plugin, LangGraphPlugin)
    assert len(plugin.activities) == 1
    assert len(interceptors) == 1
    assert isinstance(interceptors[0], CoderActivityHeartbeatInterceptor)
    assert CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT.total_seconds() > 0
    assert CODER_ACTIVITY_HEARTBEAT_TIMEOUT.total_seconds() > 0
    assert CODER_ACTIVITY_RETRY_POLICY.maximum_attempts == 1
    assert "experimental" in (LangGraphPlugin.__doc__ or "").lower()


@pytest.mark.asyncio
async def test_temporal_contract_round_trips_through_supported_converter():
    request = _request()
    result = CoderTemporalResult(
        operation_id=request.operation_id,
        messages=[{"type": "ai", "content": "Completed"}],
        workspace=request.workspace,
        execution_manifest={
            "filesystem_origin": "native_custodian",
            "selected_repository": request.workspace,
            "command_runtime": "native_custodian_host",
            "host_worker": "unavailable",
        },
        coding_session_id="coding-v1-session",
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


def test_temporal_path_does_not_change_product_registration_or_add_bridge():
    backend = Path(coding_agent.__file__).parent.parent
    langgraph = json.loads((backend / "langgraph.json").read_text())
    chat_ui = (backend / "src" / "chat_ui.py").read_text()
    temporal_sources = "\n".join(
        path.read_text() for path in (backend / "src").glob("coder_temporal*.py")
    )

    assert langgraph["graphs"] == {"chat_ui": "./src/chat_ui.py:create_chat_ui"}
    assert "create_coding_agent_graph()" in chat_ui
    assert "langgraph_sdk" not in temporal_sources
    assert "Agent Server" not in temporal_sources
    assert not (
        backend.parent
        / "openspec/changes/phase-2-coder-graph-registration/specs/independent-coder-registration"
    ).exists()
