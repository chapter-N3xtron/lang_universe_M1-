"""Fixed pending-interrupt and host-native confirmation boundaries."""

from __future__ import annotations

import http.client
import ipaddress
import json
import subprocess
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from .models import DockerSandboxAction, HostOperationPlan, HostOperationRequest
from .policy import ExecutionPlan


class PendingInterruptChecker(Protocol):
    def is_pending(
        self, thread_id: str, interrupt_id: str, plan_digest: str
    ) -> bool: ...


class ConfirmationProvider(Protocol):
    def confirm(self, request: HostOperationRequest, plan: ExecutionPlan) -> bool: ...


class AgentServerPendingInterruptChecker:
    """Read pending state directly from one fixed loopback Agent Server."""

    _MAX_RESPONSE_BYTES = 256 * 1024

    def __init__(self, base_url: str, timeout_seconds: float = 2.0):
        parsed = urlsplit(base_url)
        try:
            host = parsed.hostname or ""
            loopback = ipaddress.ip_address(host).is_loopback
            port = parsed.port or 80
        except ValueError:
            loopback = False
            port = 0
        if (
            parsed.scheme != "http"
            or not loopback
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or not (0 < port <= 65535)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "Agent Server URL must be an exact numeric loopback HTTP base URL"
            )
        self.base_url = base_url.rstrip("/")
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def is_pending(self, thread_id: str, interrupt_id: str, plan_digest: str) -> bool:
        if not thread_id or not interrupt_id or not _is_sha256(plan_digest):
            return False
        path = f"/threads/{quote(thread_id, safe='')}/state"
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout_seconds
        )
        try:
            connection.request("GET", path, headers={"Accept": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                return False
            content_length = response.getheader("Content-Length")
            if content_length is not None:
                if not content_length.isascii() or not content_length.isdecimal():
                    return False
                if int(content_length) > self._MAX_RESPONSE_BYTES:
                    return False
            body = response.read(self._MAX_RESPONSE_BYTES + 1)
            if len(body) > self._MAX_RESPONSE_BYTES:
                return False
            state = json.loads(
                body,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_json_constant,
            )
            return _state_has_plan(
                state,
                thread_id=thread_id,
                interrupt_id=interrupt_id,
                plan_digest=plan_digest,
            )
        except (
            OSError,
            http.client.HTTPException,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValidationError,
            ValueError,
        ):
            return False
        finally:
            connection.close()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _state_has_plan(
    state: Any, *, thread_id: str, interrupt_id: str, plan_digest: str
) -> bool:
    if not isinstance(state, dict):
        return False
    checkpoint = state.get("checkpoint")
    tasks = state.get("tasks")
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("thread_id") != thread_id
        or not isinstance(tasks, list)
    ):
        return False

    matches: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            return False
        interrupts = task.get("interrupts")
        if not isinstance(interrupts, list):
            return False
        for interrupt in interrupts:
            if not isinstance(interrupt, dict):
                return False
            if interrupt.get("id") == interrupt_id:
                matches.append(interrupt)
    if len(matches) != 1:
        return False

    value = matches[0].get("value")
    if not isinstance(value, dict):
        return False
    action_requests = value.get("action_requests")
    if not isinstance(action_requests, list):
        return False
    actions = [
        action
        for action in action_requests
        if isinstance(action, dict)
        and action.get("name") == "request_macos_host_operation"
    ]
    if len(actions) != 1 or "args" not in actions[0]:
        return False
    args = actions[0]["args"]
    if not isinstance(args, dict):
        return False
    encoded_args = json.dumps(
        args, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    plan = HostOperationPlan.model_validate_json(encoded_args)
    if isinstance(plan.action, DockerSandboxAction):
        values = state.get("values")
        if (
            not isinstance(values, dict)
            or values.get("workspace") != plan.action.workspace
        ):
            return False
    return plan.digest == plan_digest


class ConfirmationHelper:
    """Invoke only the fixed, trusted AppKit helper with canonical JSON on stdin."""

    def __init__(self, executable: Path):
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("confirmation helper must be an absolute regular file")
        self.executable = executable.resolve(strict=True)

    def confirm(self, request: HostOperationRequest, plan: ExecutionPlan) -> bool:
        operation = request.plan
        payload = {
            "schema_version": 1,
            "plan_digest": operation.digest,
            "request_id": request.request_id,
            "thread_id": request.thread_id,
            "interrupt_id": request.interrupt_id,
            "action": operation.action.model_dump(mode="json"),
            "expected_mutations": [
                item.model_dump(mode="json") for item in operation.expected_mutations
            ],
            "privilege": operation.privilege,
            "timeout_seconds": operation.timeout_seconds,
            "output_limit_bytes": operation.output_limit_bytes,
            "rollback": operation.rollback.model_dump(mode="json"),
            "expiry_seconds": operation.expiry_seconds,
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat(),
            "execution": {
                "category": operation.action.category,
                "executable": plan.executable,
                "argv": list(plan.argv),
                "working_directory": plan.working_directory,
                "approved_paths": list(plan.approved_paths),
            },
        }
        result = subprocess.run(
            (str(self.executable),),
            input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            shell=False,
            timeout=120,
            check=False,
        )
        try:
            response = json.loads(result.stdout[:4096])
        except json.JSONDecodeError:
            return False
        return result.returncode == 0 and response == {
            "decision": "approve",
            "plan_digest": operation.digest,
        }
