"""Serializable contracts for Temporal's outer Coder orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CODER_AGENT_SERVER_ACTIVITY_NAME = "invoke_agent_server_coder"
CODER_AGENT_SERVER_GRAPH_ID = "coder"
CoderTemporalStatus = Literal["completed", "blocked", "error"]


@dataclass(frozen=True)
class CoderTemporalRequest:
    operation_id: str
    thread_id: str
    messages: list[dict[str, Any]]
    workspace: str
    model: str | None
    execution_mode: str
    user_identity: str


@dataclass(frozen=True)
class CoderTemporalResult:
    operation_id: str
    thread_id: str
    messages: list[dict[str, str]]
    workspace: str
    execution_manifest: dict[str, str]
    coding_status: CoderTemporalStatus
    ui: list[dict[str, Any]]
