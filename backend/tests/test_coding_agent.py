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


def test_compose_change_tool_builds_global_file_options_before_subcommand(
    monkeypatch, tmp_path
):
    from src import coding_agent

    calls = []

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def action(self, action, **payload):
            calls.append((action, payload))
            return {
                "ok": True,
                "exit_code": 0,
                "output": "created",
                "truncated": False,
            }

    monkeypatch.setattr(coding_agent, "CustodianClient", Client)
    tools = coding_agent.create_custodian_boundary_tools(tmp_path)
    compose_tool = next(
        tool for tool in tools if tool.name == "custodian_compose_change"
    )

    result = compose_tool.invoke(
        {
            "compose_files": ["local-deployment-sandbox/compose.yaml"],
            "subcommand": "up",
            "arguments": ["-d", "--build", "--wait"],
            "timeout": 300,
        }
    )

    assert "created" in result
    assert calls == [
        (
            "compose_change",
            {
                "argv": [
                    "--file",
                    "local-deployment-sandbox/compose.yaml",
                    "up",
                    "-d",
                    "--build",
                    "--wait",
                ],
                "timeout": 300,
            },
        )
    ]


def test_compose_environment_tool_never_returns_generated_values(monkeypatch, tmp_path):
    from src import coding_agent

    calls = []

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def action(self, action, **payload):
            calls.append((action, payload))
            return {
                "ok": True,
                "generated": 3,
                "required": 3,
                "values_exposed": False,
            }

    monkeypatch.setattr(coding_agent, "CustodianClient", Client)
    tools = coding_agent.create_custodian_boundary_tools(tmp_path)
    environment_tool = next(
        tool
        for tool in tools
        if tool.name == "custodian_compose_prepare_environment"
    )

    result = environment_tool.invoke(
        {"compose_file": "local-deployment-sandbox/compose.yaml"}
    )

    assert "3 newly generated value(s)" in result
    assert "credential values were returned" in result
    assert calls == [
        (
            "compose_prepare_environment",
            {"compose_file": "local-deployment-sandbox/compose.yaml"},
        )
    ]


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

    assert result["messages"][:2] == output[:2]
    assert result["messages"][-1].content.startswith("Completion report")
    assert "Repository summary" in result["messages"][-1].content
    assert "native_custodian_host" in result["messages"][-1].content
    assert result["execution_manifest"]["selected_repository"] == str(
        tmp_path.resolve()
    )
    assert result["workspace"] == str(tmp_path.resolve())
    assert result["coding_session_id"] == coding_agent.coding_session_id(
        thread_identity="thread-7", workspace=tmp_path
    )
    assert result["coding_status"] == "completed"


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
    assert "relative/path" not in result["messages"][0].content


def test_host_only_workspace_is_forwarded_without_container_probe(monkeypatch, tmp_path):
    from src import coding_agent

    host_only = tmp_path / "missing-in-agent-container"
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    assert coding_agent._validated_workspace(str(host_only)) == host_only


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
    assert "sensitive-provider-detail" not in result["messages"][0].content


def test_build_deep_agent_is_workspace_confined_and_read_only(monkeypatch, tmp_path):
    from src import coding_agent

    captured = {}

    class TodoMiddleware:
        pass

    class Backend:
        def __init__(self, workspace, *, read_only):
            captured["custodian_backend"] = {
                "workspace": workspace,
                "read_only": read_only,
            }

    def create_agent(**kwargs):
        captured["agent"] = kwargs
        return SimpleNamespace()

    model = SimpleNamespace()
    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (TodoMiddleware, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model)
    monkeypatch.setattr(coding_agent, "CustodianBackend", Backend)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: True)

    coding_agent._build_deep_agent(tmp_path.resolve(), "ollama/qwen3.5:27b")

    assert captured["custodian_backend"] == {
        "workspace": str(tmp_path.resolve()),
        "read_only": True,
    }
    assert captured["agent"]["model"] is model
    assert captured["agent"]["checkpointer"] is None
    assert captured["agent"]["tools"] == []
    assert captured["agent"]["interrupt_on"] is None
    assert captured["agent"]["permissions"] is None
    assert len(captured["agent"]["middleware"]) == 1
    assert isinstance(captured["agent"]["middleware"][0], TodoMiddleware)


def test_build_deep_agent_approval_mode_uses_only_native_custodian(monkeypatch, tmp_path):
    from src import coding_agent

    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    captured = {}

    class TodoMiddleware:
        pass

    class Backend:
        def __init__(self, workspace, *, read_only):
            captured["custodian_backend"] = {
                "workspace": workspace,
                "read_only": read_only,
            }

    def create_agent(**kwargs):
        captured["agent"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(
        coding_agent,
        "_deep_agent_components",
        lambda: (TodoMiddleware, create_agent),
    )
    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: SimpleNamespace())
    monkeypatch.setattr(coding_agent, "CustodianBackend", Backend)
    monkeypatch.setattr("src.workspace_policy.host_worker_available", lambda: True)

    coding_agent._build_deep_agent(
        tmp_path.resolve(),
        "ollama/qwen3.5:27b",
        execution_mode="approval",
    )

    assert captured["custodian_backend"] == {
        "workspace": str(tmp_path.resolve()),
        "read_only": False,
    }
    assert [tool.name for tool in captured["agent"]["tools"]] == [
        "custodian_compose_prepare_environment",
        "custodian_compose_read",
        "custodian_compose_change",
        "custodian_github_publish",
    ]
    assert set(captured["agent"]["interrupt_on"]) == {
        "write_file",
        "edit_file",
        "delete",
        "execute",
        "custodian_compose_read",
        "custodian_github_publish",
    }
    assert captured["agent"]["permissions"] is None
    assert captured["agent"]["skills"] is None
    assert len(captured["agent"]["middleware"]) == 1
    assert isinstance(captured["agent"]["middleware"][0], TodoMiddleware)
    system_prompt = captured["agent"]["system_prompt"]
    assert "Never search parent, child, or sibling" in system_prompt
    assert "native_custodian_host" in system_prompt
    assert "direct Custodian worker: available" in system_prompt
    assert "request_macos_host_operation" in system_prompt
    assert "built-in execute tool" in system_prompt
    assert "normal shell, Git, build, test, package, and host commands" in system_prompt
    assert "not inside the Agent Server container" in system_prompt
    assert "explicit human task requires work elsewhere on the host" in system_prompt
    assert "use execute with that absolute path" in system_prompt
    assert "custodian_github_publish" in system_prompt
    assert "chapter-N3xtron" in system_prompt
    assert "write_todos" in system_prompt
    assert "OpenSpec artifacts as planning context, not as a second" in system_prompt
    assert "proceed even when an OpenSpec change is incomplete" in system_prompt
    assert "including requested builds and service restarts" in system_prompt
    assert "custodian_compose_prepare_environment" in system_prompt
    assert "Never ask the human to provide those local values" in system_prompt
    assert "must never be reported as blockers" in system_prompt
    assert "Use execute for ordinary command work" in system_prompt
    assert "15-minute report" in system_prompt
    assert "Completion report" in system_prompt

    coding_agent._build_deep_agent(
        tmp_path.resolve(),
        "ollama/qwen3.5:27b",
        execution_mode="autonomous",
    )

    assert captured["agent"]["permissions"] is None
    assert set(captured["agent"]["interrupt_on"]) == {
        "custodian_github_publish",
    }


def test_coding_graph_uses_deep_agents_node():
    from src import coding_agent

    graph = coding_agent.create_coding_agent_graph()
    assert "coding_agent" in graph.get_graph().nodes


def test_stream_session_reports_every_interval_and_clears_final_card(monkeypatch):
    from src import coding_agent

    class StreamingApp:
        async def astream(self, _payload, config=None, stream_mode=None):
            yield {
                "todos": [
                    {"content": "Inspect the change", "status": "in_progress"}
                ]
            }
            await asyncio.sleep(0.025)
            yield {
                "todos": [
                    {"content": "Inspect the change", "status": "completed"}
                ]
            }

    published = []
    deleted = []

    def push(name, props, *, id=None, state_key=None):
        event = {"id": id or "progress-1", "name": name, "props": props}
        published.append((event, state_key))
        return event

    def delete(message_id, *, state_key):
        deleted.append((message_id, state_key))

    monkeypatch.setattr(coding_agent, "push_ui_message", push)
    monkeypatch.setattr(coding_agent, "delete_ui_message", delete)

    result = asyncio.run(
        coding_agent._stream_session(
            StreamingApp(),
            {"messages": []},
            {},
            report_interval_seconds=0.01,
        )
    )

    assert len(published) == 2
    assert published[0][0]["name"] == "coder_progress_report"
    assert published[0][0]["props"]["elapsed_minutes"] == 15
    assert published[0][0]["props"]["tasks"][0]["status"] == "in_progress"
    assert published[1][0]["id"] == published[0][0]["id"]
    assert deleted == [("progress-1", "ui")]
    assert result["todos"][0]["status"] == "completed"


def test_completion_report_lists_each_task_with_a_note():
    from src import coding_agent

    report = coding_agent._completion_report_text(
        "Changed the requested file and ran its test.",
        [
            {"content": "Change the file", "status": "completed"},
            {"content": "Run the live check", "status": "pending"},
        ],
    )

    assert report.startswith("Completion report")
    assert "Completed: Change the file. Note:" in report
    assert "Not completed: Run the live check. Note:" in report
    assert "Coder notes" in report


def test_progress_report_includes_declared_blockers():
    from src import coding_agent

    report = coding_agent._progress_report_props(
        [
            {
                "content": "BLOCKER: Waiting for the required approval",
                "status": "pending",
            }
        ],
        report_number=3,
    )

    assert report["elapsed_minutes"] == 45
    assert report["blockers"] == ["Waiting for the required approval"]
