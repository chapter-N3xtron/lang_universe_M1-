from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActivateRequest(StrictModel):
    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    owner_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    workspace: str = Field(min_length=1, max_length=2048)
    lease_seconds: int = Field(default=14400, ge=300, le=43200)


class ActivateResponse(StrictModel):
    status: Literal["active"]
    lease_token: str
    expires_at: str
    workspace: str
    scope_digest: str
    policy_version: str


class RevokeResponse(StrictModel):
    status: Literal["revoked", "not_active"]


class ComposeTarget(StrictModel):
    project_directory: str = Field(default=".", min_length=1, max_length=1024)
    compose_files: list[str] = Field(min_length=1, max_length=1)


class ComposeInspectRequest(ComposeTarget):
    workspace: str = Field(min_length=1, max_length=2048)
    inspection: Literal["config_summary", "service_status"] = "config_summary"


class DockerOperationPlan(StrictModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, strict=True, frozen=True
    )

    request_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    project_directory: str = Field(min_length=1, max_length=1024)
    compose_files: list[str] = Field(min_length=1, max_length=1)
    operation: Literal["pull", "build", "up", "start", "stop", "restart", "down"]
    services: list[str] = Field(default_factory=list, max_length=40)
    profiles: list[str] = Field(default_factory=list, max_length=20)

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json.encode()).hexdigest()


class ComposeApplyRequest(DockerOperationPlan):
    pass


class ConfirmationAttempt(StrictModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, strict=True, frozen=True
    )

    thread_id: str = Field(min_length=1, max_length=256)
    interrupt_id: str = Field(min_length=1, max_length=256)
    plan: DockerOperationPlan


OperationLifecycle = Literal[
    "requested", "confirming", "running", "succeeded", "failed", "rejected"
]
TerminalOperationState = Literal["succeeded", "failed", "rejected"]


class CoderOperationStatus(StrictModel):
    operation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: OperationLifecycle
    result_available: bool


class CoderConfirmationResponse(CoderOperationStatus):
    pass


class CoderOperationResult(StrictModel):
    operation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: TerminalOperationState
    result: dict[str, JsonValue]


class ServiceSummary(StrictModel):
    name: str
    image: str | None = None
    build: bool
    published_ports: list[str] = Field(default_factory=list)
    state: str | None = None


class ComposeInspectResponse(StrictModel):
    valid: bool
    project: str
    services: list[ServiceSummary]
    policy_version: str


class ComposeApplyResponse(StrictModel):
    request_id: str
    status: Literal["succeeded"]
    operation: str
    project: str
    services: list[str]


class RuntimeInspectResponse(StrictModel):
    name: str
    image: str
    status: str
    health: str | None = None
    platform: str | None = None
    ports: list[str] = Field(default_factory=list)
    networks: list[str] = Field(default_factory=list)
    mounts: list[dict[str, str | bool]] = Field(default_factory=list)
    docker_socket_present: bool
    privileged: bool
    host_namespaces_present: bool
    devices_present: bool


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: Literal["docker-broker"]
    docker_available: bool
    policy_version: str
    boot_id: str
