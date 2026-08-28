"""Runtime identity checks for Agent Server-owned checkpoint state."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class RuntimeIdentityError(ValueError):
    pass


def _bounded(value: Any) -> str:
    return str(value or "")[:128]


def authoritative_thread_id(
    declared_thread_id: Any,
    config: RunnableConfig | None,
    *,
    operation: str,
) -> str:
    configurable = (config or {}).get("configurable", {})
    runtime_thread_id = str(configurable.get("thread_id") or "")
    declared = str(declared_thread_id or "")

    if runtime_thread_id and declared and runtime_thread_id != declared:
        logger.error(
            "Agent Server thread identity conflict",
            extra={
                "authority_source": "agent_server_postgresql",
                "operation": _bounded(operation),
                "runtime_thread_id": _bounded(runtime_thread_id),
                "declared_thread_id": _bounded(declared),
                "reason": "thread_identity_mismatch",
            },
        )
        raise RuntimeIdentityError(
            "Agent Server thread identity conflicts with the declared thread identity."
        )

    thread_id = runtime_thread_id or declared
    if not thread_id:
        logger.error(
            "Agent Server thread identity is missing",
            extra={
                "authority_source": "agent_server_postgresql",
                "operation": _bounded(operation),
                "reason": "thread_identity_missing",
            },
        )
        raise RuntimeIdentityError("Agent Server thread identity is required.")
    return thread_id
