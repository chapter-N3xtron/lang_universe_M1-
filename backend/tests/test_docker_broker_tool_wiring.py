"""Coding-agent and deployment wiring for brokered host Docker operations."""

from __future__ import annotations

from types import SimpleNamespace

from src.runtime_identity import runtime_identity
from src.workspace_policy import execution_manifest


def _capture_agent(monkeypatch):
    from src import coding_agent

    captured = []

    class Component:
        def __init__(self, **_values):
            pass

    def create_agent(**values):
        captured.append(values)
        return SimpleNamespace()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (Component, Component, Component, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: SimpleNamespace())
    return coding_agent, captured


def test_docker_tool_wiring_by_execution_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCKER_BROKER_URL", "http://host.docker.internal:8766")
    coding_agent, captured = _capture_agent(monkeypatch)

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="approval")
    approval = captured[-1]
    assert [tool.name for tool in approval["tools"]] == [
        "request_docker_compose_operation"
    ]
    assert approval["interrupt_on"]["request_docker_compose_operation"][
        "allowed_decisions"
    ] == ["approve", "reject"]

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="autonomous")
    autonomous = captured[-1]
    assert [tool.name for tool in autonomous["tools"]] == [
        "request_docker_compose_operation"
    ]
    assert set(autonomous["interrupt_on"]) == {
        "request_docker_compose_operation"
    }
    assert "For every Docker or Docker Compose task" in autonomous["system_prompt"]
    assert (
        "Never call request_macos_host_operation to inspect"
        in autonomous["system_prompt"]
    )
    assert (
        "never use Mac inspection as a Docker preflight" in autonomous["system_prompt"]
    )
    assert "one Docker request alone per assistant turn" in autonomous["system_prompt"]

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="read_only")
    assert captured[-1]["tools"] == []
    assert captured[-1]["interrupt_on"] is None


def test_host_and_docker_tools_coexist(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    key = tmp_path / "receipt-signing.pub"
    key.write_bytes(public)
    key.chmod(0o444)
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE", str(key))
    monkeypatch.setenv("DOCKER_BROKER_URL", "http://host.docker.internal:8766")
    coding_agent, captured = _capture_agent(monkeypatch)
    coding_agent._build_deep_agent(tmp_path, None, execution_mode="autonomous")
    assert [tool.name for tool in captured[-1]["tools"]] == [
        "request_macos_host_operation",
        "request_docker_compose_operation",
    ]
    assert set(captured[-1]["interrupt_on"]) == {
        "request_macos_host_operation",
        "request_docker_compose_operation",
    }


def test_manifest_and_runtime_identity_report_broker_availability(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    monkeypatch.setenv("DOCKER_BROKER_URL", "http://host.docker.internal:8766")
    assert execution_manifest(tmp_path)["docker_broker_request"] == "available"
    assert runtime_identity()["docker_broker_request"] == "available"


def test_compose_has_only_non_secret_broker_url_and_no_docker_authority():
    from pathlib import Path

    compose = (Path(__file__).parents[1] / "docker-compose.override.yml").read_text()
    assert "DOCKER_BROKER_URL=http://host.docker.internal:8766" in compose
    assert "DOCKER_BROKER_TOKEN" not in compose
    assert "DOCKER_BROKER_SECRET" not in compose
    assert "/var/run/docker.sock" not in compose
