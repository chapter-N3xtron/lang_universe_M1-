"""Automatic heartbeats for the outer Agent Server invocation activity."""

from __future__ import annotations

import asyncio

from temporalio import activity
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
)

from src.coder_temporal_contract import CODER_AGENT_SERVER_ACTIVITY_NAME

CODER_TEMPORAL_ACTIVITY_TYPE = CODER_AGENT_SERVER_ACTIVITY_NAME


class _CoderActivityHeartbeatInboundInterceptor(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput):
        info = activity.info()
        if (
            info.activity_type != CODER_TEMPORAL_ACTIVITY_TYPE
            or info.heartbeat_timeout is None
        ):
            return await self.next.execute_activity(input)

        interval = info.heartbeat_timeout.total_seconds() / 2

        async def heartbeat_until_complete() -> None:
            while True:
                activity.heartbeat()
                await asyncio.sleep(interval)

        heartbeat_task = asyncio.create_task(heartbeat_until_complete())
        try:
            return await self.next.execute_activity(input)
        finally:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)


class CoderActivityHeartbeatInterceptor(Interceptor):
    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return _CoderActivityHeartbeatInboundInterceptor(next)
