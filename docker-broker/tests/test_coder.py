from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from docker_broker.api import create_app
from docker_broker.coder import CoderOperationManager
from docker_broker.errors import ApprovalRejected
from docker_broker.langgraph import _pending_workspace
from docker_broker.models import ConfirmationAttempt, DockerOperationPlan
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


class Checker:
    def __init__(self, workspace: Path | None) -> None:
        self.workspace = workspace
        self.calls = 0

    def pending_workspace(self, _attempt: ConfirmationAttempt) -> str | None:
        self.calls += 1
        return str(self.workspace) if self.workspace else None


class Confirmation:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.calls = 0

    async def approve(self, **_values) -> None:
        self.calls += 1
        if not self.approved:
            raise ApprovalRejected("rejected")


class BlockingConfirmation:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def approve(self, **_values) -> None:  # type: ignore[no-untyped-def]
        self.started.set()
        await self.release.wait()


class Runner:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []

    async def apply(self, project, request, _lease):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("secret stderr")
        return {
            "request_id": request.request_id,
            "status": "succeeded",
            "operation": request.operation,
            "project": project.project_name,
            "services": ["web"],
        }

    async def docker_available(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def write_project(repository: Path) -> None:
    stack = repository / "stack"
    stack.mkdir()
    (stack / "compose.yaml").write_text(
        yaml.safe_dump(
            {"services": {"web": {"image": "busybox@sha256:" + "0" * 64}}}
        )
    )


def plan(request_id: str = "request-one", operation: str = "up") -> dict:
    return {
        "request_id": request_id,
        "project_directory": "stack",
        "compose_files": ["compose.yaml"],
        "operation": operation,
        "services": [],
        "profiles": [],
    }


def attempt(request_id: str = "request-one") -> ConfirmationAttempt:
    return ConfirmationAttempt(
        thread_id="thread-one",
        interrupt_id="interrupt-one",
        plan=DockerOperationPlan.model_validate(plan(request_id)),
    )


def state_for(value: ConfirmationAttempt, workspace: Path) -> dict:
    return {
        "checkpoint": {"thread_id": value.thread_id},
        "values": {"workspace": str(workspace)},
        "tasks": [
            {
                "interrupts": [
                    {
                        "id": value.interrupt_id,
                        "value": {
                            "action_requests": [
                                {
                                    "name": "request_docker_compose_operation",
                                    "args": value.plan.model_dump(mode="json"),
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }


def test_plan_schema_is_strict_and_digest_is_canonical() -> None:
    left = DockerOperationPlan.model_validate(plan())
    right = DockerOperationPlan.model_validate(
        dict(reversed(list(plan().items())))
    )
    assert left.digest == right.digest
    assert len(left.compose_files) == 1
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate({**plan(), "unexpected": True})
    without_project_directory = plan()
    without_project_directory.pop("project_directory")
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate(without_project_directory)
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate({**plan(), "compose_files": []})
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate({**plan(), "services": "web"})


def test_operation_digest_matches_backend_golden_vector() -> None:
    value = ConfirmationAttempt(
        thread_id="thread-one",
        interrupt_id="interrupt-one",
        plan=DockerOperationPlan.model_validate(
            {
                "request_id": "req-1",
                "project_directory": ".",
                "compose_files": ["docker-compose.yml"],
                "operation": "up",
                "services": [],
                "profiles": [],
            }
        ),
    )
    assert CoderOperationManager.operation_digest(
        Path("/Volumes/Storage/example"), value
    ) == "3c8d437b9aa3494205727c214cb028fe96d40a866e746870fb4b96b89e7c9b2a"


def test_pending_state_requires_exact_interrupt_action_plan_and_workspace(
    repository: Path,
) -> None:
    value = attempt()
    state = state_for(value, repository)
    assert _pending_workspace(state, value) == str(repository)
    state["tasks"].append({"interrupts": []})
    state["tasks"][1]["interrupts"].append(
        {"id": "another", "value": {"action_requests": []}}
    )
    assert _pending_workspace(state, value) is None
    mismatched = state_for(value, repository)
    mismatched["checkpoint"]["thread_id"] = "another"
    assert _pending_workspace(mismatched, value) is None
    mismatched = state_for(value, repository)
    mismatched["tasks"][0]["interrupts"][0]["value"]["action_requests"][0][
        "args"
    ]["request_id"] = "changed"
    assert _pending_workspace(mismatched, value) is None


async def wait_for_result(client: AsyncClient, digest: str) -> dict:
    terminal = {"succeeded", "failed", "rejected"}
    for _ in range(100):
        status_response = await client.get(f"/v1/coder/status/{digest}")
        assert status_response.status_code == 200
        status = status_response.json()
        assert set(status) == {
            "operation_digest",
            "plan_digest",
            "state",
            "result_available",
        }
        if status["state"] in terminal:
            assert status["result_available"] is True
            response = await client.get(f"/v1/coder/results/{digest}")
            assert response.status_code == 200
            result = response.json()
            assert set(result) == {
                "operation_digest",
                "plan_digest",
                "state",
                "result",
            }
            assert result["operation_digest"] == status["operation_digest"]
            assert result["plan_digest"] == status["plan_digest"]
            assert result["state"] == status["state"]
            return result
        assert status["result_available"] is False
        await asyncio.sleep(0.01)
    raise AssertionError("operation did not finish")


@pytest.mark.asyncio
async def test_result_fails_closed_until_terminal(settings, repository: Path) -> None:
    write_project(repository)
    confirmation = BlockingConfirmation()
    app = create_app(
        settings,
        confirmation=confirmation,  # type: ignore[arg-type]
        runner=Runner(),  # type: ignore[arg-type]
        pending_checker=Checker(repository),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/v1/coder/confirmations", json=attempt().model_dump()
        )
        digest = response.json()["operation_digest"]
        await asyncio.wait_for(confirmation.started.wait(), timeout=1)
        status = (await client.get(f"/v1/coder/status/{digest}")).json()
        assert status["state"] == "confirming"
        assert status["result_available"] is False
        unavailable = await client.get(f"/v1/coder/results/{digest}")
        assert unavailable.status_code == 422
        assert unavailable.json() == {
            "error": {
                "code": "policy_rejected",
                "message": "Operation result is unavailable",
            }
        }
        confirmation.release.set()
        assert (await wait_for_result(client, digest))["state"] == "succeeded"


@pytest.mark.asyncio
async def test_public_boundary_idempotency_and_lease_reuse(
    settings, repository: Path
) -> None:
    write_project(repository)
    checker = Checker(repository)
    confirmation = Confirmation()
    runner = Runner()
    app = create_app(
        settings,
        confirmation=confirmation,
        runner=runner,  # type: ignore[arg-type]
        pending_checker=checker,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "docker-broker"
        assert (await client.get("/v1/health")).status_code == 401
        first = await client.post("/v1/coder/confirmations", json=attempt().model_dump())
        assert first.status_code == 200
        first_status = first.json()
        assert set(first_status) == {
            "operation_digest",
            "plan_digest",
            "state",
            "result_available",
        }
        assert first_status["plan_digest"] == attempt().plan.digest
        assert first_status["state"] == "requested"
        assert first_status["result_available"] is False
        digest = first_status["operation_digest"]
        result = await wait_for_result(client, digest)
        assert result == {
            "operation_digest": digest,
            "plan_digest": attempt().plan.digest,
            "state": "succeeded",
            "result": {
                "request_id": "request-one",
                "operation": "up",
                "project": result["result"]["project"],
                "services": ["web"],
                "message": "Operation succeeded",
            },
        }
        repeated = await client.post(
            "/v1/coder/confirmations", json=attempt().model_dump()
        )
        assert repeated.json()["operation_digest"] == digest
        second = await client.post(
            "/v1/coder/confirmations", json=attempt("request-two").model_dump()
        )
        await wait_for_result(client, second.json()["operation_digest"])
        assert confirmation.calls == 1
        assert len(runner.requests) == 2
        text = result.__repr__() + first.text + repeated.text + second.text
        assert settings.client_secret not in text
        assert "lease_token" not in text
        cors = await client.options(
            "/v1/coder/confirmations",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert cors.headers["access-control-allow-origin"] == "http://localhost:3001"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("approved", "runner_fails", "expected"),
    [(False, False, "rejected"), (True, True, "failed")],
)
async def test_coder_terminal_failure_is_generic(
    settings, repository: Path, approved: bool, runner_fails: bool, expected: str
) -> None:
    write_project(repository)
    app = create_app(
        settings,
        confirmation=Confirmation(approved),
        runner=Runner(runner_fails),  # type: ignore[arg-type]
        pending_checker=Checker(repository),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/v1/coder/confirmations", json=attempt().model_dump()
        )
        result = await wait_for_result(client, response.json()["operation_digest"])
        assert result["state"] == expected
        assert result["result"] == {
            "request_id": "request-one",
            "operation": "up",
            "message": (
                "Operation was rejected" if expected == "rejected" else "Operation failed"
            ),
        }
        assert "secret stderr" not in str(result)
        assert settings.client_secret not in str(result)


@pytest.mark.asyncio
async def test_builds_require_flag(settings, repository: Path) -> None:
    write_project(repository)
    runner = Runner()
    disabled = replace(settings, allow_builds=False)
    app = create_app(
        disabled,
        confirmation=Confirmation(),
        runner=runner,  # type: ignore[arg-type]
        pending_checker=Checker(repository),
    )
    body = ConfirmationAttempt(
        thread_id="thread-one",
        interrupt_id="interrupt-one",
        plan=DockerOperationPlan.model_validate(plan(operation="build")),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/v1/coder/confirmations", json=body.model_dump()
        )
        result = await wait_for_result(client, response.json()["operation_digest"])
        assert result["state"] == "failed"
        assert result["result"] == {
            "request_id": "request-one",
            "operation": "build",
            "message": "Operation failed",
        }
        assert not runner.requests
    assert 8765 in settings.reserved_ports
    assert 8766 in settings.reserved_ports
