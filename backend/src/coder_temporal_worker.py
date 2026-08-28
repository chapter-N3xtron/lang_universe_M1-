"""Temporal worker for outer Agent Server Coder orchestration."""

from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Interceptor, Worker

from src.coder_agent_server_activity import invoke_agent_server_coder
from src.coder_temporal_heartbeat import CoderActivityHeartbeatInterceptor
from src.coder_temporal_workflow import (
    CODER_ACTIVITY_HEARTBEAT_TIMEOUT,
    CODER_ACTIVITY_RETRY_POLICY,
    CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT,
    CoderTemporalWorkflow,
)

CODER_TEMPORAL_TASK_QUEUE = "coder"


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
        activities=[invoke_agent_server_coder],
        interceptors=create_coder_temporal_interceptors(),
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_coder_temporal_worker())


__all__ = [
    "CODER_ACTIVITY_HEARTBEAT_TIMEOUT",
    "CODER_ACTIVITY_RETRY_POLICY",
    "CODER_ACTIVITY_START_TO_CLOSE_TIMEOUT",
    "create_coder_temporal_interceptors",
    "run_coder_temporal_worker",
]
