from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from docker_broker.api import create_app
from docker_broker.audit import AuditLog
from docker_broker.runner import DockerRunner
from httpx import ASGITransport, AsyncClient


class Confirmation:
    async def approve(self, **_values) -> None:
        return None


def project(repository: Path) -> None:
    directory = repository / "stack"
    directory.mkdir()
    (directory / "compose.yaml").write_text(
        yaml.safe_dump(
            {
                "services": {
                    "web": {
                        "image": "busybox@sha256:" + "0" * 64,
                        "ports": ["127.0.0.1:18080:8080"],
                    }
                }
            }
        )
    )


@pytest.mark.asyncio
async def test_api_is_fail_closed_and_sanitizes_runtime(settings, repository):
    project(repository)
    app = create_app(settings, confirmation=Confirmation())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Broker-Client-Secret": settings.client_secret or ""},
    ) as client:
        denied = await client.post(
            "/v1/compose/apply",
            json={
                "request_id": "request-one",
                "project_directory": "stack",
                "compose_files": ["compose.yaml"],
                "operation": "up",
                "services": [],
                "profiles": [],
            },
        )
        assert denied.status_code == 403
        activated = await client.post(
            "/v1/sessions/activate",
            json={
                "session_id": "thread-one",
                "owner_id": "owner-one",
                "workspace": str(repository),
                "lease_seconds": 300,
            },
        )
        assert activated.status_code == 200
        token = activated.json()["lease_token"]
        applied = await client.post(
            "/v1/compose/apply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "request_id": "request-one",
                "project_directory": "stack",
                "compose_files": ["compose.yaml"],
                "operation": "up",
                "services": [],
                "profiles": [],
            },
        )
        assert applied.status_code == 200
        inspected = await client.get("/v1/runtime/langgraph")
        assert inspected.status_code == 200
        payload = inspected.json()
        assert payload["image"] == "jasper-langgraph:current"
        assert payload["mounts"] == [
            {"type": "bind", "destination": "/workspace", "read_write": True}
        ]
        assert "SECRET" not in inspected.text
        revoked = await client.post(
            "/v1/sessions/revoke",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert revoked.json()["status"] == "revoked"
        denied_again = await client.post(
            "/v1/compose/apply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "request_id": "request-two",
                "project_directory": "stack",
                "compose_files": ["compose.yaml"],
                "operation": "down",
                "services": [],
                "profiles": [],
            },
        )
        assert denied_again.status_code == 403


@pytest.mark.asyncio
async def test_down_never_deletes_volumes(settings, repository, fake_docker):
    project(repository)
    executable, log = fake_docker
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    app = create_app(settings, confirmation=Confirmation(), runner=runner)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Broker-Client-Secret": settings.client_secret or ""},
    ) as client:
        activated = await client.post(
            "/v1/sessions/activate",
            json={
                "session_id": "thread-two",
                "owner_id": "owner-one",
                "workspace": str(repository),
                "lease_seconds": 300,
            },
        )
        token = activated.json()["lease_token"]
        response = await client.post(
            "/v1/compose/apply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "request_id": "request-down",
                "project_directory": "stack",
                "compose_files": ["compose.yaml"],
                "operation": "down",
                "services": [],
                "profiles": [],
            },
        )
        assert response.status_code == 200
    commands = log.read_text()
    assert "--volumes" not in commands
    assert "--rmi" not in commands
    assert "--remove-orphans" not in commands
    assert str(executable) not in commands
