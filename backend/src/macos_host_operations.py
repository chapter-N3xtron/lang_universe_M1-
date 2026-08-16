"""Receipt-only bridge to the separately operated macOS host executor.

This module deliberately has no confirmation, cancellation, or execution client.  The
only network operation it can perform is retrieval of an already-created receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from langchain_core.tools import StructuredTool, ToolException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

StrictText = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
AbsolutePath = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^/")
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_MAX_RECEIPT_BYTES = 256 * 1024
_MAX_RESULT_TEXT = 4096
_ENV_ENDPOINT = "MACOS_HOST_EXECUTOR_URL"
_ENV_PUBLIC_KEY = "MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE"
_SECRET = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|password|secret|private[_ -]?key)\s*[:=]\s*\S+)"
)


class HostOperationError(ToolException, ValueError):
    """Stable, non-sensitive failure returned by the receipt-only tool."""


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
        parsed = urllib.parse.urlsplit(value)
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
    """Exact mirror of the executor's model-facing immutable plan."""

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
    """Match the executor's RFC-8785-compatible integer/string subset."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class HostOperatorConfig:
    endpoint: str
    public_key: bytes
    key_id: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class ReceiptClient:
    """Fixed GET-only client; it cannot initiate or cancel host execution."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 5.0):
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def fetch(self, digest: str) -> bytes:
        url = f"{self._endpoint}/v1/receipts/{digest}"
        request = urllib.request.Request(  # noqa: S310 -- operator-fixed URL
            url, headers={"Accept": "application/json"}, method="GET"
        )
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > _MAX_RECEIPT_BYTES:
                    raise HostOperationError("host_receipt_too_large")
                body = response.read(_MAX_RECEIPT_BYTES + 1)
        except HostOperationError:
            raise
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise HostOperationError("host_receipt_unavailable") from exc
        if len(body) > _MAX_RECEIPT_BYTES:
            raise HostOperationError("host_receipt_too_large")
        return body


def _validate_endpoint(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("invalid receipt endpoint")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("invalid receipt endpoint") from exc
    return value.rstrip("/")


def load_operator_config() -> HostOperatorConfig | None:
    """Validate non-secret operator inputs and otherwise fail closed."""

    endpoint = os.getenv(_ENV_ENDPOINT)
    key_name = os.getenv(_ENV_PUBLIC_KEY)
    if not endpoint and not key_name:
        return None
    if not endpoint or not key_name:
        return None
    try:
        endpoint = _validate_endpoint(endpoint)
        key_path = Path(key_name)
        if not key_path.is_absolute():
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(key_path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o222:
                return None
            public_key = os.read(descriptor, 33)
        finally:
            os.close(descriptor)
        if len(public_key) != 32:
            return None
        Ed25519PublicKey.from_public_bytes(public_key)
    except (OSError, ValueError):
        return None
    return HostOperatorConfig(
        endpoint=endpoint,
        public_key=public_key,
        key_id=hashlib.sha256(public_key).hexdigest()[:16],
    )


def host_operation_request_available() -> bool:
    return load_operator_config() is not None


def _verify_receipt(
    body: bytes,
    plan: HostOperationPlan,
    config: HostOperatorConfig,
    *,
    now: datetime | None = None,
) -> Receipt:
    try:
        signed = SignedReceipt.model_validate_json(body)
        if signed.key_id != config.key_id:
            raise HostOperationError("host_receipt_key_mismatch")
        signature = base64.b64decode(signed.signature, validate=True)
        Ed25519PublicKey.from_public_bytes(config.public_key).verify(
            signature,
            canonical_json_bytes(signed.receipt.model_dump(mode="json")),
        )
    except HostOperationError:
        raise
    except (InvalidSignature, ValueError) as exc:
        raise HostOperationError("host_receipt_unverifiable") from exc

    receipt = signed.receipt
    if receipt.request_digest != plan.digest:
        raise HostOperationError("host_receipt_digest_mismatch")
    if receipt.action_category != plan.action.category:
        raise HostOperationError("host_receipt_category_mismatch")
    if not receipt.terminal_status.terminal:
        raise HostOperationError("host_receipt_nonterminal")
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    if receipt.finished_at.tzinfo is None or receipt.finished_at.utcoffset() is None:
        raise HostOperationError("host_receipt_unverifiable")
    if receipt.finished_at.astimezone(UTC) > instant:
        raise HostOperationError("host_receipt_unverifiable")
    succeeded = receipt.terminal_status is LifecycleState.SUCCEEDED
    if receipt.verified_outcome is not succeeded:
        raise HostOperationError("host_receipt_outcome_mismatch")
    return receipt


def _safe_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _SECRET.sub("[REDACTED]", value)[:_MAX_RESULT_TEXT]


def _redacted_result(receipt: Receipt) -> str:
    """Return bounded facts only; process output, argv, paths, and IDs stay private."""

    result = {
        "source": "verified_macos_host_receipt",
        "request_digest": receipt.request_digest,
        "terminal_status": receipt.terminal_status.value,
        "action_category": receipt.action_category,
        "verified_outcome": receipt.verified_outcome,
        "finished_at": receipt.finished_at.isoformat(),
        "output_truncated": receipt.process.output_truncated,
        "timed_out": receipt.process.timed_out,
        "cancelled": receipt.process.cancelled,
        "remaining_human_step": _safe_text(receipt.remaining_human_step),
        "message": _safe_text(receipt.message),
    }
    return canonical_json_bytes(result).decode("utf-8")


def fetch_and_verify_receipt(
    plan: HostOperationPlan,
    config: HostOperatorConfig,
    *,
    client: ReceiptClient | None = None,
    now: datetime | None = None,
) -> str:
    body = (client or ReceiptClient(config.endpoint)).fetch(plan.digest)
    return _redacted_result(_verify_receipt(body, plan, config, now=now))


class _HostOperationTool(StructuredTool):
    """Parse LLM JSON in JSON mode while retaining a strict mirrored model.

    Pydantic strict tuple fields intentionally reject Python lists, whereas the wire
    contract correctly accepts JSON arrays. LangChain normally validates a decoded
    dict in Python mode, so this narrow override restores the executor's JSON-mode
    semantics without weakening scalar coercion or extra-field rejection.
    """

    def _parse_input(
        self, tool_input: str | dict, tool_call_id: str | None
    ) -> str | dict[str, object]:
        del tool_call_id
        if not isinstance(tool_input, dict):
            raise HostOperationError("invalid_host_operation_plan")
        plan = HostOperationPlan.model_validate_json(json.dumps(tool_input))
        return plan.model_dump()


def create_request_macos_host_operation_tool(
    config: HostOperatorConfig,
) -> StructuredTool:
    """Create the one receipt-only tool exposed to Coding after HITL approval."""

    def request_macos_host_operation(**values: object) -> str:
        plan = HostOperationPlan.model_validate(values)
        return fetch_and_verify_receipt(plan, config)

    return _HostOperationTool.from_function(
        func=request_macos_host_operation,
        name="request_macos_host_operation",
        description=(
            "Request review of one immutable typed macOS host-operation plan. After "
            "approval, this tool only retrieves and verifies the executor's existing "
            "signed terminal receipt; it never starts host execution."
        ),
        args_schema=HostOperationPlan,
    )
