from __future__ import annotations

import http.client
import ipaddress
import json
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from docker_broker.models import ConfirmationAttempt, DockerOperationPlan


class PendingInterruptChecker(Protocol):
    def pending_workspace(self, attempt: ConfirmationAttempt) -> str | None: ...


class AgentServerPendingInterruptChecker:
    _MAX_RESPONSE_BYTES = 256 * 1024

    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
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
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def pending_workspace(self, attempt: ConfirmationAttempt) -> str | None:
        path = f"/threads/{quote(attempt.thread_id, safe='')}/state"
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout_seconds
        )
        try:
            connection.request("GET", path, headers={"Accept": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                return None
            content_length = response.getheader("Content-Length")
            if content_length is not None and (
                not content_length.isascii()
                or not content_length.isdecimal()
                or int(content_length) > self._MAX_RESPONSE_BYTES
            ):
                return None
            body = response.read(self._MAX_RESPONSE_BYTES + 1)
            if len(body) > self._MAX_RESPONSE_BYTES:
                return None
            state = json.loads(
                body,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_json_constant,
            )
            return _pending_workspace(state, attempt)
        except (
            OSError,
            http.client.HTTPException,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValidationError,
            ValueError,
        ):
            return None
        finally:
            connection.close()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _pending_workspace(state: Any, attempt: ConfirmationAttempt) -> str | None:
    if not isinstance(state, dict):
        return None
    checkpoint = state.get("checkpoint")
    tasks = state.get("tasks")
    values = state.get("values")
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("thread_id") != attempt.thread_id
        or not isinstance(tasks, list)
        or not isinstance(values, dict)
    ):
        return None

    interrupts: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("interrupts"), list):
            return None
        for interrupt in task["interrupts"]:
            if not isinstance(interrupt, dict):
                return None
            interrupts.append(interrupt)
    if len(interrupts) != 1 or interrupts[0].get("id") != attempt.interrupt_id:
        return None

    value = interrupts[0].get("value")
    if not isinstance(value, dict):
        return None
    action_requests = value.get("action_requests")
    if not isinstance(action_requests, list):
        return None
    actions = [
        action
        for action in action_requests
        if isinstance(action, dict)
        and action.get("name") == "request_docker_compose_operation"
    ]
    if len(actions) != 1 or not isinstance(actions[0].get("args"), dict):
        return None
    encoded = json.dumps(
        actions[0]["args"], ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    plan = DockerOperationPlan.model_validate_json(encoded)
    if plan.digest != attempt.plan.digest:
        return None
    workspace = values.get("workspace")
    if not isinstance(workspace, str) or not 1 <= len(workspace) <= 2048:
        return None
    return workspace
