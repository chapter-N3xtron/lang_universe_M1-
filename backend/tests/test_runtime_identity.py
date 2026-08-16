from src.runtime_identity import runtime_identity


def test_runtime_identity_fails_closed_without_deployment_marker(monkeypatch):
    monkeypatch.delenv("SESSION_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("SESSION_RUNTIME_ID", raising=False)

    assert runtime_identity() == {
        "runtime_id": "unverified",
        "durable": False,
        "persistence": "unverified",
        "command_runtime": "linux_agent_server_container",
        "native_host_operations": "unavailable_without_separate_approval",
        "host_operation_request": "unavailable",
        "docker_sandbox_request": "unavailable",
    }


def test_runtime_identity_reports_docker_postgres_marker(monkeypatch):
    monkeypatch.setenv("SESSION_RUNTIME_MODE", "durable")
    monkeypatch.setenv("SESSION_RUNTIME_ID", "backend-postgres-v1")

    assert runtime_identity() == {
        "runtime_id": "backend-postgres-v1",
        "durable": True,
        "persistence": "postgres",
        "command_runtime": "linux_agent_server_container",
        "native_host_operations": "unavailable_without_separate_approval",
        "host_operation_request": "unavailable",
        "docker_sandbox_request": "unavailable",
    }
