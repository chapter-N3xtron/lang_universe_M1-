"""Receipt-only integration for Docker Compose operations requested through the broker.

The client in this module can only retrieve the terminal result for an immutable
operation. It has no API for creating, approving, cancelling, or otherwise
controlling broker operations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.tools import StructuredTool, ToolException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

RequestId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
]
TargetText = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Operation = Literal["pull", "build", "up", "start", "stop", "restart", "down"]
TerminalState = Literal["succeeded", "failed", "rejected", "cancelled", "expired"]

_ENV_ENDPOINT = "DOCKER_BROKER_URL"
_MAX_RESPONSE_BYTES = 64 * 1024
_MAX_RESULT_BYTES = 32 * 1024
_MAX_TEXT_LENGTH = 4096
_MAX_COLLECTION_ITEMS = 100
_ENDPOINT_HOST = re.compile(r"^[A-Za-z0-9._:-]+$")
_SECRET_KEY = re.compile(
    r"(?i)(authorization|cookie|credential|password|secret|token|private[_-]?key)"
)
_SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|password|secret|private[_ -]?key)\s*[:=]\s*\S+)"
)


class DockerBrokerOperationError(ToolException, ValueError):
    """Stable, non-sensitive failure from the result-only broker integration."""


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, str_strip_whitespace=True
    )


class DockerOperationPlan(StrictModel):
    """Exact model-facing Compose operation plan mirrored from the broker contract."""

    request_id: RequestId
    project_directory: TargetText
    compose_files: tuple[TargetText, ...] = Field(min_length=1, max_length=1)
    operation: Operation
    services: tuple[TargetText, ...] = Field(default=(), max_length=40)
    profiles: tuple[TargetText, ...] = Field(default=(), max_length=20)

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.model_dump(mode="json"))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class DockerOperationResult(StrictModel):
    """Terminal result envelope returned by the broker's Coder result endpoint."""

    operation_digest: Sha256
    plan_digest: Sha256
    state: TerminalState
    result: JsonValue

    @model_validator(mode="after")
    def object_result(self) -> DockerOperationResult:
        if not isinstance(self.result, dict):
            raise ValueError("result must be a JSON object")
        return self


@dataclass(frozen=True)
class DockerBrokerConfig:
    endpoint: str

    @property
    def identity(self) -> str:
        return self.endpoint


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class DockerBrokerResultClient:
    """Fixed GET-only result client; it cannot initiate a Docker operation."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 5.0):
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def fetch(self, operation_digest: str) -> bytes:
        url = f"{self._endpoint}/v1/coder/results/{operation_digest}"
        request = urllib.request.Request(  # noqa: S310 -- operator-fixed base URL
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > _MAX_RESPONSE_BYTES:
                    raise DockerBrokerOperationError("docker_broker_result_too_large")
                body = response.read(_MAX_RESPONSE_BYTES + 1)
        except DockerBrokerOperationError:
            raise
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise DockerBrokerOperationError("docker_broker_result_unavailable") from exc
        if len(body) > _MAX_RESPONSE_BYTES:
            raise DockerBrokerOperationError("docker_broker_result_too_large")
        return body


def canonical_json_bytes(value: object) -> bytes:
    """Encode the contract's deterministic canonical JSON subset."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def operation_digest(plan: DockerOperationPlan, workspace: str | Path) -> str:
    """Bind a complete normalized plan to one canonical absolute workspace."""

    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        raise DockerBrokerOperationError("invalid_docker_broker_workspace")
    canonical = str(workspace_path.resolve())
    envelope = {
        "plan": plan.model_dump(mode="json"),
        "workspace": canonical,
    }
    return hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()


def _validate_endpoint(value: str) -> str:
    if value != value.strip():
        raise ValueError("invalid Docker broker endpoint")
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid Docker broker endpoint") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or port is None
        or port < 1
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not _ENDPOINT_HOST.fullmatch(parsed.hostname)
        or value.rstrip("/") != f"{parsed.scheme}://{parsed.netloc}"
    ):
        raise ValueError("invalid Docker broker endpoint")
    try:
        parsed.hostname.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("invalid Docker broker endpoint") from exc
    return value.rstrip("/")


def load_docker_broker_config() -> DockerBrokerConfig | None:
    """Load the sole non-secret setting, failing closed on any invalid value."""

    endpoint = os.getenv(_ENV_ENDPOINT)
    if not endpoint:
        return None
    try:
        return DockerBrokerConfig(endpoint=_validate_endpoint(endpoint))
    except ValueError:
        return None


def docker_broker_request_available() -> bool:
    return load_docker_broker_config() is not None


def _sanitize(value: object, *, depth: int = 0) -> object:
    if depth >= 8:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return _SECRET_TEXT.sub("[REDACTED]", value)[:_MAX_TEXT_LENGTH]
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, list):
        return [
            _sanitize(item, depth=depth + 1)
            for item in value[:_MAX_COLLECTION_ITEMS]
        ]
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key in sorted(value)[:_MAX_COLLECTION_ITEMS]:
            safe_key = str(key)[:256]
            sanitized[safe_key] = (
                "[REDACTED]"
                if _SECRET_KEY.search(safe_key)
                else _sanitize(value[key], depth=depth + 1)
            )
        return sanitized
    return "[REDACTED]"


def validate_and_sanitize_result(
    body: bytes,
    plan: DockerOperationPlan,
    workspace: str | Path,
) -> str:
    """Validate result binding and return only bounded, sanitized canonical JSON."""

    expected_operation_digest = operation_digest(plan, workspace)
    try:
        envelope = DockerOperationResult.model_validate_json(body)
    except (ValueError, TypeError) as exc:
        raise DockerBrokerOperationError("invalid_docker_broker_result") from exc
    if envelope.operation_digest != expected_operation_digest:
        raise DockerBrokerOperationError("docker_broker_operation_digest_mismatch")
    if envelope.plan_digest != plan.digest:
        raise DockerBrokerOperationError("docker_broker_plan_digest_mismatch")

    safe = _sanitize(envelope.model_dump(mode="json"))
    try:
        encoded = canonical_json_bytes(safe)
    except (TypeError, ValueError) as exc:
        raise DockerBrokerOperationError("invalid_docker_broker_result") from exc
    if len(encoded) > _MAX_RESULT_BYTES:
        safe = {
            "operation_digest": envelope.operation_digest,
            "plan_digest": envelope.plan_digest,
            "state": envelope.state,
            "result": {"truncated": True},
        }
        encoded = canonical_json_bytes(safe)
    return encoded.decode("utf-8")


def fetch_docker_broker_result(
    plan: DockerOperationPlan,
    workspace: str | Path,
    config: DockerBrokerConfig,
    *,
    client: DockerBrokerResultClient | None = None,
) -> str:
    digest = operation_digest(plan, workspace)
    body = (client or DockerBrokerResultClient(config.endpoint)).fetch(digest)
    return validate_and_sanitize_result(body, plan, workspace)


class _DockerOperationTool(StructuredTool):
    """Restore strict Pydantic JSON-array semantics for LangChain tool input."""

    def _parse_input(
        self, tool_input: str | dict, tool_call_id: str | None
    ) -> str | dict[str, object]:
        del tool_call_id
        if not isinstance(tool_input, dict):
            raise DockerBrokerOperationError("invalid_docker_operation_plan")
        try:
            plan = DockerOperationPlan.model_validate_json(json.dumps(tool_input))
        except (ValueError, TypeError) as exc:
            raise DockerBrokerOperationError("invalid_docker_operation_plan") from exc
        return plan.model_dump()


def create_request_docker_compose_operation_tool(
    config: DockerBrokerConfig,
    workspace: str | Path,
) -> StructuredTool:
    """Create the result-only tool with workspace authority held in its closure."""

    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        raise DockerBrokerOperationError("invalid_docker_broker_workspace")
    canonical_workspace = str(workspace_path.resolve())

    def request_docker_compose_operation(**values: object) -> str:
        plan = DockerOperationPlan.model_validate(values)
        return fetch_docker_broker_result(plan, canonical_workspace, config)

    return _DockerOperationTool.from_function(
        func=request_docker_compose_operation,
        name="request_docker_compose_operation",
        description=(
            "Request review of one immutable Docker Compose operation plan for the "
            "selected host workspace. After approval, this tool only retrieves the "
            "broker's existing terminal result; it never sends a Docker command."
        ),
        args_schema=DockerOperationPlan,
    )
