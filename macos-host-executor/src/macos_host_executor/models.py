"""Strict wire contract for the finite host action catalog."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

StrictText = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
CorrelationId = Annotated[str, StringConstraints(min_length=1, max_length=256)]
AbsolutePath = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^/")
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Privilege(StrEnum):
    USER = "user"


class LifecycleState(StrEnum):
    REQUESTED = "requested"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"

    @property
    def terminal(self) -> bool:
        return self in {
            self.SUCCEEDED,
            self.FAILED,
            self.REJECTED,
            self.EXPIRED,
            self.CANCELLED,
            self.PARTIAL,
            self.UNCERTAIN,
        }


class Mutation(StrictModel):
    operation: Literal["create", "replace", "remove", "inspect"]
    path: AbsolutePath
    detail: StrictText


class RollbackLimits(StrictModel):
    strategy: Literal["none", "remove_created_destination", "detach_only"]
    removes_only_request_created_paths: bool = True
    may_require_human_inspection: bool


class InputHash(StrictModel):
    path: AbsolutePath
    sha256: Sha256


class HostInspectionAction(StrictModel):
    category: Literal["host_inspection"]
    query: Literal[
        "macos_version",
        "architecture",
        "disk_space",
        "path_metadata",
        "application_presence",
        "application_version",
    ]
    target_path: AbsolutePath | None = None
    application_id: StrictText | None = None

    @model_validator(mode="after")
    def required_selector(self) -> HostInspectionAction:
        if self.query in {"disk_space", "path_metadata"} and not self.target_path:
            raise ValueError("query requires target_path")
        if self.query.startswith("application_") and not self.application_id:
            raise ValueError("query requires application_id")
        if self.query not in {"disk_space", "path_metadata"} and self.target_path:
            raise ValueError("target_path is not valid for this query")
        return self


class DownloadAction(StrictModel):
    category: Literal["https_download"]
    url: StrictText
    destination: AbsolutePath
    sha256: Sha256
    max_bytes: int = Field(ge=1, le=2_147_483_648)
    redirect_limit: int = Field(default=0, ge=0, le=3)
    archive: Literal["none", "dmg", "zip", "tar_gz"] = "none"

    @field_validator("url")
    @classmethod
    def exact_https_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "an exact credential-free HTTPS URL without query or fragment is required"
            )
        return value


class HomebrewAction(StrictModel):
    category: Literal["homebrew"]
    operation: Literal["install", "uninstall"]
    package_kind: Literal["formula", "cask"]
    package: Annotated[
        str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9@+._-]{0,127}$")
    ]


class ApplicationInstallAction(StrictModel):
    category: Literal["application_install"]
    artifact_path: AbsolutePath
    artifact_sha256: Sha256
    artifact_kind: Literal["dmg", "zip"]
    application_id: StrictText
    destination: AbsolutePath
    mode: Literal["stage", "install"]
    require_team_id: StrictText
    require_notarization: bool = True


class NativeApplicationAction(StrictModel):
    category: Literal["native_application"]
    application_id: StrictText
    operation: Literal["blender_background_render", "blender_version"]
    working_directory: AbsolutePath
    input_path: AbsolutePath | None = None
    output_path: AbsolutePath | None = None
    script: InputHash | None = None
    configuration: tuple[InputHash, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def render_requirements(self) -> NativeApplicationAction:
        if self.operation == "blender_background_render":
            if not self.input_path or not self.output_path:
                raise ValueError("render requires input_path and output_path")
        elif self.input_path or self.output_path or self.script or self.configuration:
            raise ValueError("version operation accepts no mutable inputs or outputs")
        return self


ComposeIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    ),
]
RelativePath = Annotated[str, StringConstraints(min_length=1, max_length=4096)]


class DockerSandboxAction(StrictModel):
    category: Literal["docker_sandbox"]
    workspace: AbsolutePath
    project_directory: RelativePath
    compose_file: RelativePath
    compose_sha256: Sha256
    operation: Literal["pull", "build", "up", "start", "stop", "restart", "down", "ps"]
    services: tuple[ComposeIdentifier, ...] = Field(default=(), max_length=64)
    profiles: tuple[ComposeIdentifier, ...] = Field(default=(), max_length=32)

    @field_validator("project_directory", "compose_file")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        if "\x00" in value or "\\" in value:
            raise ValueError("relative path contains a prohibited character")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("path must be relative and may not traverse parents")
        return value

    @model_validator(mode="after")
    def operation_constraints(self) -> DockerSandboxAction:
        if self.operation == "down" and self.services:
            raise ValueError("down does not accept services")
        return self


HostAction = Annotated[
    HostInspectionAction
    | DownloadAction
    | HomebrewAction
    | ApplicationInstallAction
    | NativeApplicationAction
    | DockerSandboxAction,
    Field(discriminator="category"),
]


class HostOperationPlan(StrictModel):
    """The complete immutable, model-facing authority for one host operation."""

    action: HostAction
    expected_mutations: tuple[Mutation, ...] = Field(max_length=32)
    privilege: Literal[Privilege.USER] = Privilege.USER
    timeout_seconds: int = Field(ge=1, le=3600)
    output_limit_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)
    rollback: RollbackLimits
    expiry_seconds: int = Field(ge=1, le=3600)

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.model_dump(mode="json"))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class ConfirmationAttempt(StrictModel):
    """UI envelope correlating an immutable plan to an actual pending interrupt."""

    thread_id: CorrelationId
    interrupt_id: CorrelationId
    plan: HostOperationPlan


class HostOperationRequest(StrictModel):
    """Executor-produced request metadata wrapped around an authority-bearing plan."""

    schema_version: Literal[1] = 1
    request_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
    thread_id: CorrelationId
    interrupt_id: CorrelationId
    plan: HostOperationPlan
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_server_window(self) -> HostOperationRequest:
        seconds = (self.expires_at - self.created_at).total_seconds()
        if seconds != self.plan.expiry_seconds:
            raise ValueError("server expiry must exactly match plan expiry_seconds")
        return self

    @classmethod
    def from_attempt(
        cls, attempt: ConfirmationAttempt, *, now: datetime | None = None
    ) -> HostOperationRequest:
        created_at = (now or datetime.now(UTC)).astimezone(UTC)
        return cls(
            request_id=str(uuid.uuid4()),
            thread_id=attempt.thread_id,
            interrupt_id=attempt.interrupt_id,
            plan=attempt.plan,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=attempt.plan.expiry_seconds),
        )

    @property
    def digest(self) -> str:
        """The idempotency and receipt digest is always the plan digest."""
        return self.plan.digest

    def assert_unexpired(self, now: datetime | None = None) -> None:
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        if instant >= self.expires_at:
            raise ValueError("request expired")


class ProcessSummary(StrictModel):
    pid: int | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    timed_out: bool = False
    cancelled: bool = False


class RollbackReport(StrictModel):
    attempted: bool = False
    succeeded: bool | None = None
    detail: str = "not required"


class Receipt(StrictModel):
    schema_version: Literal[1] = 1
    request_digest: Sha256
    request_id: str
    terminal_status: LifecycleState
    started_at: datetime | None = None
    finished_at: datetime
    action_category: str
    executable: str
    argv_summary: tuple[str, ...]
    working_directory: str | None = None
    approved_paths: tuple[str, ...] = ()
    observed_paths: tuple[str, ...] = ()
    artifact_hashes: tuple[InputHash, ...] = ()
    process: ProcessSummary = ProcessSummary()
    verified_outcome: bool = False
    observed_mutations: tuple[Mutation, ...] = ()
    rollback: RollbackReport = RollbackReport()
    remaining_human_step: str | None = None
    message: str = ""

    @model_validator(mode="after")
    def terminal_only(self) -> Receipt:
        if not self.terminal_status.terminal:
            raise ValueError("receipts must be terminal")
        return self


class SignedReceipt(StrictModel):
    receipt: Receipt
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: StrictText
    signature: StrictText


def canonical_json_bytes(value: object) -> bytes:
    """RFC-8785-compatible for this integer/string-only contract subset."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
