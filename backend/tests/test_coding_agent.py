"""Focused tests for the provider-neutral Deep Agents coding subgraph."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage


class _FakeApp:
    def __init__(self, output_messages):
        self.output_messages = output_messages

    async def aget_state(self, _config):
        return SimpleNamespace(values={}, tasks=(), created_at=None)

    async def ainvoke(self, payload, config=None):
        return {"messages": [*payload["messages"], *self.output_messages]}


def test_deep_agents_node_returns_neutral_messages_events_and_session(
    monkeypatch, tmp_path
):
    from src import coding_agent

    output = [
        AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {}, "id": "call-1"}],
        ),
        ToolMessage(content="contents", tool_call_id="call-1"),
        AIMessage(content="Repository summary"),
    ]

    async def session_agent(*_args):
        return _FakeApp(output)

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)

    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Inspect this repo"}],
                "workspace": str(tmp_path),
                "model": "ollama/qwen3.5:27b",
                "execution_mode": "read_only",
                "thread_identity": "thread-7",
            }
        )
    )

    assert result["messages"] == output
    assert result["coding_session_id"] == coding_agent.coding_session_id(
        thread_identity="thread-7", workspace=tmp_path
    )
    assert result["coding_status"] == "completed"
    assert [event["status"] for event in result["coding_events"]] == [
        "running",
        "running",
        "completed",
        "completed",
    ]
    assert all(event["type"] == "coding_event" for event in result["coding_events"])
    assert result["coding_events"][1]["data"] == {
        "name": "read_file",
        "tool_call_id": "call-1",
    }


def test_deep_agents_node_does_not_complete_without_final_assistant_message(
    monkeypatch, tmp_path
):
    from src import coding_agent

    output = [
        AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {}, "id": "call-1"}],
        ),
        ToolMessage(content="contents", tool_call_id="call-1"),
    ]

    async def session_agent(*_args):
        return _FakeApp(output)

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)

    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Inspect this repo"}],
                "workspace": str(tmp_path),
                "execution_mode": "read_only",
                "thread_identity": "missing-final",
            }
        )
    )

    assert result["coding_status"] == "error"
    assert "missing_final_result" in result["messages"][0].content
    assert result["coding_events"][-1]["data"]["code"] == "missing_final_result"


def test_deep_agents_node_rejects_relative_workspace(monkeypatch):
    from src import coding_agent

    build = MagicMock()
    monkeypatch.setattr(coding_agent, "_build_deep_agent", build)
    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Inspect"}],
                "workspace": "relative/path",
                "thread_identity": "thread-invalid",
            }
        )
    )

    build.assert_not_called()
    assert result["coding_status"] == "error"
    assert result["coding_events"][-1]["kind"] == "error"
    assert result["coding_events"][-1]["data"]["code"] == "invalid_workspace"
    assert "relative/path" not in result["messages"][0].content


def test_deep_agents_node_classifies_missing_workspace(monkeypatch, tmp_path):
    from src import coding_agent

    build = MagicMock()
    monkeypatch.setattr(coding_agent, "_build_deep_agent", build)
    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Inspect"}],
                "workspace": str(tmp_path / "missing"),
                "thread_identity": "thread-missing",
            }
        )
    )

    build.assert_not_called()
    assert result["coding_status"] == "error"
    assert result["coding_events"][-1]["data"]["code"] == "invalid_workspace"


def test_deep_agents_node_sanitizes_agent_failure(monkeypatch, tmp_path):
    from src import coding_agent

    class FailingApp:
        async def aget_state(self, _config):
            return SimpleNamespace(values={}, tasks=(), created_at=None)

        async def ainvoke(self, _payload, config=None):
            raise RuntimeError("sensitive-provider-detail")

    async def session_agent(*_args):
        return FailingApp()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "Inspect"}],
                "workspace": str(tmp_path),
                "thread_identity": "thread-failure",
            }
        )
    )

    assert result["coding_status"] == "error"
    assert result["coding_events"][-1]["data"]["code"] == "agent_failure"
    assert "sensitive-provider-detail" not in result["messages"][0].content


def test_build_deep_agent_is_workspace_confined_and_read_only(monkeypatch, tmp_path):
    from src import coding_agent

    captured = {}

    class Permission:
        def __init__(self, **kwargs):
            self.operations = kwargs["operations"]
            self.paths = kwargs["paths"]
            self.mode = kwargs["mode"]

    class FilesystemBackend:
        def __init__(self, **kwargs):
            captured["filesystem_backend"] = kwargs

    class LocalShellBackend:
        def __init__(self, **kwargs):
            captured["local_shell_backend"] = kwargs

    def create_agent(**kwargs):
        captured["agent"] = kwargs
        return SimpleNamespace()

    model = SimpleNamespace()
    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (Permission, FilesystemBackend, LocalShellBackend, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model)

    coding_agent._build_deep_agent(tmp_path.resolve(), "ollama/qwen3.5:27b")

    assert captured["filesystem_backend"] == {
        "root_dir": tmp_path.resolve(),
        "virtual_mode": True,
    }
    assert captured["agent"]["model"] is model
    assert captured["agent"]["checkpointer"] is False
    assert captured["agent"]["tools"] == []
    assert captured["agent"]["interrupt_on"] is None
    permissions = captured["agent"]["permissions"]
    assert permissions[0].operations == ["read", "write"]
    assert "/.env" in permissions[0].paths
    assert permissions[0].mode == "deny"
    assert (permissions[1].operations, permissions[1].paths, permissions[1].mode) == (
        ["read"],
        ["/**"],
        "allow",
    )
    assert (permissions[2].operations, permissions[2].paths, permissions[2].mode) == (
        ["write"],
        ["/**"],
        "deny",
    )


def test_build_deep_agent_approval_mode_uses_native_local_shell(monkeypatch, tmp_path):
    from src import coding_agent

    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    captured = {}

    class Permission:
        def __init__(self, **kwargs):
            self.operations = kwargs["operations"]
            self.paths = kwargs["paths"]
            self.mode = kwargs["mode"]

    class FilesystemBackend:
        def __init__(self, **kwargs):
            captured["filesystem_backend"] = kwargs

    class LocalShellBackend:
        def __init__(self, **kwargs):
            captured["local_shell_backend"] = kwargs

    def create_agent(**kwargs):
        captured["agent"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (Permission, FilesystemBackend, LocalShellBackend, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: SimpleNamespace())

    coding_agent._build_deep_agent(
        tmp_path.resolve(),
        "ollama/qwen3.5:27b",
        execution_mode="approval",
    )

    assert captured["local_shell_backend"] == {
        "root_dir": tmp_path.resolve(),
        "virtual_mode": True,
        "timeout": 120,
        "max_output_bytes": 100_000,
        "env": {
            "PATH": (
                "/opt/coding-tools/node/bin:/opt/coding-tools/pnpm:"
                + coding_agent.os.environ.get("PATH", "")
            ),
            "NPM_CONFIG_PREFIX": "/opt/coding-tools/node",
            "PNPM_HOME": "/opt/coding-tools/pnpm",
        },
        "inherit_env": True,
    }
    assert captured["agent"]["tools"] == []
    assert set(captured["agent"]["interrupt_on"]) == {
        "write_file",
        "edit_file",
        "delete",
        "execute",
    }
    assert captured["agent"]["permissions"] is None
    assert captured["agent"]["skills"] == ["/.agents/skills/"]


def test_coding_graph_uses_deep_agents_node():
    from src import coding_agent

    graph = coding_agent.create_coding_agent_graph()
    assert "coding_agent" in graph.get_graph().nodes
