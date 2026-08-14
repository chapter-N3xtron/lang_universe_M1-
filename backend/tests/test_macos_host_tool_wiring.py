"""Coding-agent wiring tests for the one standard HITL host request tool."""

from __future__ import annotations

from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _configure_operator(monkeypatch, tmp_path):
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    key = tmp_path / "receipt-signing.pub"
    key.write_bytes(public)
    key.chmod(0o444)
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE", str(key))


def _capture_agent(monkeypatch):
    from src import coding_agent

    captured = []

    class Permission:
        def __init__(self, **values):
            self.values = values

    class Backend:
        def __init__(self, **_values):
            pass

    def create_agent(**values):
        captured.append(values)
        return SimpleNamespace()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (Permission, Backend, Backend, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: SimpleNamespace())
    return coding_agent, captured


def test_host_tool_is_available_only_with_valid_operator_config(monkeypatch, tmp_path):
    from src.workspace_policy import execution_manifest

    assert execution_manifest(tmp_path)["host_operation_request"] == "unavailable"
    _configure_operator(monkeypatch, tmp_path)
    assert execution_manifest(tmp_path)["host_operation_request"] == "available"


def test_approval_mode_merges_local_approvals_and_host_approve_reject(
    monkeypatch, tmp_path
):
    _configure_operator(monkeypatch, tmp_path)
    coding_agent, captured = _capture_agent(monkeypatch)
    coding_agent._build_deep_agent(tmp_path, None, execution_mode="approval")

    values = captured[-1]
    assert [tool.name for tool in values["tools"]] == [
        "request_macos_host_operation"
    ]
    assert set(values["interrupt_on"]) == {
        "write_file",
        "edit_file",
        "delete",
        "execute",
        "request_macos_host_operation",
    }
    assert values["interrupt_on"]["request_macos_host_operation"][
        "allowed_decisions"
    ] == ["approve", "reject"]


def test_autonomous_mode_interrupts_only_host_request_and_read_only_has_no_tool(
    monkeypatch, tmp_path
):
    _configure_operator(monkeypatch, tmp_path)
    coding_agent, captured = _capture_agent(monkeypatch)

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="autonomous")
    autonomous = captured[-1]
    assert [tool.name for tool in autonomous["tools"]] == [
        "request_macos_host_operation"
    ]
    assert set(autonomous["interrupt_on"]) == {"request_macos_host_operation"}
    assert autonomous["interrupt_on"]["request_macos_host_operation"][
        "allowed_decisions"
    ] == ["approve", "reject"]

    coding_agent._build_deep_agent(tmp_path, None, execution_mode="read_only")
    read_only = captured[-1]
    assert read_only["tools"] == []
    assert read_only["interrupt_on"] is None


def test_invalid_operator_config_exposes_no_host_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    coding_agent, captured = _capture_agent(monkeypatch)
    coding_agent._build_deep_agent(tmp_path, None, execution_mode="autonomous")
    assert captured[-1]["tools"] == []
    assert captured[-1]["interrupt_on"] is None


def test_coding_graph_topology_remains_one_node_and_two_edges():
    from src.coding_agent import create_coding_agent_graph

    graph = create_coding_agent_graph().get_graph()
    assert set(graph.nodes) == {"__start__", "coding_agent", "__end__"}
    assert {(edge.source, edge.target) for edge in graph.edges} == {
        ("__start__", "coding_agent"),
        ("coding_agent", "__end__"),
    }
