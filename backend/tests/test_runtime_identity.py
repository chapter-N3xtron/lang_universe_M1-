import src.runtime_identity as runtime_identity_module
from src.runtime_identity import runtime_identity


def test_runtime_identity_fails_closed_without_deployment_marker(monkeypatch):
    monkeypatch.delenv("SESSION_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("SESSION_RUNTIME_ID", raising=False)
    monkeypatch.setenv("CUSTODIAN_WORKER_URL", "")

    assert runtime_identity() == {
        "runtime_id": "unverified",
        "durable": False,
        "persistence": "unverified",
        "command_runtime": "linux_agent_server_container",
        "host_worker": "unavailable",
    }


def test_runtime_identity_reports_docker_postgres_marker(monkeypatch):
    monkeypatch.setenv("SESSION_RUNTIME_MODE", "durable")
    monkeypatch.setenv("SESSION_RUNTIME_ID", "backend-postgres-v1")
    monkeypatch.setenv("CUSTODIAN_WORKER_URL", "http://host.docker.internal:8765")
    monkeypatch.setattr(runtime_identity_module, "host_worker_available", lambda: True)

    assert runtime_identity() == {
        "runtime_id": "backend-postgres-v1",
        "durable": True,
        "persistence": "postgres",
        "command_runtime": "linux_agent_server_container",
        "host_worker": "available",
    }
