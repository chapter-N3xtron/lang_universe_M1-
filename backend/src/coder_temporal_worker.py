"""Temporal worker registration for the authoritative Coder graph."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta

from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.contrib.langgraph import LangGraphPlugin
from temporalio.worker import Interceptor, Worker

from src.coder_temporal_heartbeat import CoderActivityHeartbeatInterceptor
from src.coder_temporal_workflow import CoderTemporalWorkflow
from src.coding_agent import create_coding_agent_graph_builder

CODER_TEMPORAL_TASK_QUEUE = "coder"
CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT = timedelta(hours=24)
CODER_ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(seconds=10)
CODER_ACTIVITY_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


def create_coder_temporal_plugin(
    *,
    start_to_close_timeout: timedelta = CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    heartbeat_timeout: timedelta = CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    retry_policy: RetryPolicy = CODER_ACTIVITY_RETRY_POLICY,
) -> LangGraphPlugin:
    return LangGraphPlugin(
        graphs={"coder": create_coding_agent_graph_builder()},
        default_activity_options={
            "start_to_close_timeout": start_to_close_timeout,
            "heartbeat_timeout": heartbeat_timeout,
            "retry_policy": retry_policy,
        },
    )


def create_coder_temporal_interceptors() -> list[Interceptor]:
    return [CoderActivityHeartbeatInterceptor()]


async def run_coder_temporal_worker() -> None:
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    worker = Worker(
        client,
        task_queue=os.getenv("TEMPORAL_CODER_TASK_QUEUE", CODER_TEMPORAL_TASK_QUEUE),
        workflows=[CoderTemporalWorkflow],
        plugins=[create_coder_temporal_plugin()],
        interceptors=create_coder_temporal_interceptors(),
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_coder_temporal_worker())
