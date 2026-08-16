"""Coding wiring for typed SBX Docker operations through the host tool."""

from __future__ import annotations

from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
    monkeypatch.setattr(
        coding_agent,
        "load_operator_config",
        lambda: SimpleNamespace(endpoint="http://127.0.0.1:8765", key_id="key"),
    )
    monkeypatch.setattr(
        coding_agent,
        "create_request_macos_host_operation_tool",
        lambda _config: SimpleNamespace(name="request_macos_host_operation"),
    )
    return coding_agent, captured


def test_docker_sandbox_uses_only_host_tool_by_execution_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCKER_BROKER_URL", "http://host.docker.internal:8766")
    coding_agent, captured = _capture_agent(monkeypatch)

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="approval")
    approval = captured[-1]
    assert [tool.name for tool in approval["tools"]] == [
        "request_macos_host_operation"
    ]
    assert set(approval["interrupt_on"]) >= {"request_macos_host_operation"}
    assert "request_docker_compose_operation" not in approval["interrupt_on"]

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="autonomous")
    autonomous = captured[-1]
    assert [tool.name for tool in autonomous["tools"]] == [
        "request_macos_host_operation"
    ]
    assert set(autonomous["interrupt_on"]) == {"request_macos_host_operation"}
    prompt = autonomous["system_prompt"]
    assert "typed docker_sandbox action" in prompt
    assert "one Docker sandbox host-operation request" in prompt
    assert "request_docker_compose_operation" not in prompt
    assert "logs, exec, raw commands, names, argv" in prompt

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="read_only")
    assert captured[-1]["tools"] == []
    assert captured[-1]["interrupt_on"] is None


def _host_config(monkeypatch, tmp_path):
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    key = tmp_path / "receipt-signing.pub"
    key.write_bytes(public)
    key.chmod(0o444)
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE", str(key))


def test_manifest_and_runtime_report_sandbox_from_host_config(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    _host_config(monkeypatch, tmp_path)
    assert execution_manifest(tmp_path)["docker_sandbox_request"] == "available"
    assert runtime_identity()["docker_sandbox_request"] == "available"


def test_legacy_broker_config_does_not_enable_coding_route(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    monkeypatch.setenv("DOCKER_BROKER_URL", "http://host.docker.internal:8766")
    assert execution_manifest(tmp_path)["docker_sandbox_request"] == "unavailable"
    assert runtime_identity()["docker_sandbox_request"] == "unavailable"
