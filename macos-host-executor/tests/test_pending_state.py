from __future__ import annotations

import copy
import json
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from macos_host_executor.confirmation import AgentServerPendingInterruptChecker
from macos_host_executor.models import HostOperationPlan


@contextmanager
def agent_server(
    body: object, *, status: int = 200, declared_length: int | None = None
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []
    encoded = json.dumps(body, separators=(",", ":")).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                }
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header(
                "Content-Length",
                str(len(encoded) if declared_length is None else declared_length),
            )
            self.end_headers()
            if declared_length is None:
                self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def pending_state(
    plan: HostOperationPlan,
    *,
    thread_id: str = "thread/actual",
    interrupt_id: str = "interrupt:one",
    action_name: str = "request_macos_host_operation",
) -> dict[str, Any]:
    return {
        "values": {},
        "next": ["agent"],
        "checkpoint": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": "checkpoint-one",
        },
        "tasks": [
            {
                "id": "task-one",
                "name": "agent",
                "interrupts": [
                    {
                        "id": interrupt_id,
                        "value": {
                            "action_requests": [
                                {
                                    "name": action_name,
                                    "args": plan.model_dump(mode="json"),
                                    "description": "Approve exact host operation",
                                }
                            ],
                            "review_configs": [],
                        },
                    }
                ],
            }
        ],
    }


def test_direct_agent_server_check_is_fixed_get_without_credentials(
    inspection_plan: HostOperationPlan,
) -> None:
    state = pending_state(inspection_plan)
    with agent_server(state) as (url, requests):
        checker = AgentServerPendingInterruptChecker(url)
        assert checker.is_pending(
            "thread/actual", "interrupt:one", inspection_plan.digest
        )

    assert len(requests) == 1
    assert requests[0]["method"] == "GET"
    assert requests[0]["path"] == "/threads/thread%2Factual/state"
    headers = {key.lower(): value for key, value in requests[0]["headers"].items()}
    assert "authorization" not in headers
    assert "cookie" not in headers


@pytest.mark.parametrize(
    ("mutation", "digest"),
    [
        (lambda state: state["checkpoint"].update(thread_id="thread-other"), None),
        (
            lambda state: state["tasks"][0]["interrupts"][0].update(
                id="interrupt-other"
            ),
            None,
        ),
        (
            lambda state: state["tasks"][0]["interrupts"][0]["value"][
                "action_requests"
            ][0].update(name="some_other_action"),
            None,
        ),
        (lambda state: None, "0" * 64),
    ],
    ids=["wrong-thread", "wrong-interrupt", "wrong-action", "wrong-digest"],
)
def test_mismatched_pending_authority_is_rejected(
    inspection_plan: HostOperationPlan, mutation, digest: str | None
) -> None:
    state = copy.deepcopy(pending_state(inspection_plan))
    mutation(state)
    with agent_server(state) as (url, _):
        checker = AgentServerPendingInterruptChecker(url)
        assert not checker.is_pending(
            "thread/actual", "interrupt:one", digest or inspection_plan.digest
        )


@pytest.mark.parametrize(
    "state",
    [
        None,
        [],
        {},
        {"checkpoint": {"thread_id": "thread/actual"}, "tasks": {}},
        {"checkpoint": {"thread_id": "thread/actual"}, "tasks": [{}]},
        {
            "checkpoint": {"thread_id": "thread/actual"},
            "tasks": [{"interrupts": [{"id": "interrupt:one", "value": []}]}],
        },
    ],
)
def test_malformed_agent_state_is_rejected(
    inspection_plan: HostOperationPlan, state: object
) -> None:
    with agent_server(state) as (url, _):
        assert not AgentServerPendingInterruptChecker(url).is_pending(
            "thread/actual", "interrupt:one", inspection_plan.digest
        )


def test_strict_plan_args_reject_extra_authority(
    inspection_plan: HostOperationPlan,
) -> None:
    state = pending_state(inspection_plan)
    args = state["tasks"][0]["interrupts"][0]["value"]["action_requests"][0]["args"]
    args["shell_command"] = "id"
    with agent_server(state) as (url, _):
        assert not AgentServerPendingInterruptChecker(url).is_pending(
            "thread/actual", "interrupt:one", inspection_plan.digest
        )


def test_oversized_agent_state_is_rejected(
    inspection_plan: HostOperationPlan,
) -> None:
    with agent_server(
        {}, declared_length=AgentServerPendingInterruptChecker._MAX_RESPONSE_BYTES + 1
    ) as (url, _):
        assert not AgentServerPendingInterruptChecker(url).is_pending(
            "thread/actual", "interrupt:one", inspection_plan.digest
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:2024",
        "http://localhost:2024",
        "http://192.0.2.10:2024",
        "http://127.0.0.1:2024/pending",
        "http://user:pass@127.0.0.1:2024",
        "http://127.0.0.1:2024?callback=http://127.0.0.1",
    ],
)
def test_agent_server_url_must_be_exact_numeric_loopback(url: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        AgentServerPendingInterruptChecker(url)


def test_unavailable_agent_server_fails_closed(
    inspection_plan: HostOperationPlan,
) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    checker = AgentServerPendingInterruptChecker(
        f"http://127.0.0.1:{port}", timeout_seconds=0.1
    )
    assert not checker.is_pending(
        "thread/actual", "interrupt:one", inspection_plan.digest
    )
