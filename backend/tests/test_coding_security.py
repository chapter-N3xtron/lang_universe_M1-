"""Security and human-approval tests for the Deep Agents coding backend."""

import asyncio
import os
from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command
from pydantic import PrivateAttr


class ToolCallingModel(BaseChatModel):
    _responses: list[AIMessage] = PrivateAttr()

    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)

    @property
    def _llm_type(self):
        return "security-test"

    def bind_tools(self, _tools, **_kwargs):
        return self

    def _generate(self, _messages, stop=None, run_manager=None, **_kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._responses.pop(0))])


def _write_model(file_path="/approved.txt", content="approved"):
    return ToolCallingModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {"file_path": file_path, "content": content},
                        "id": "write-1",
                    }
                ],
            ),
            AIMessage(content="finished"),
        ]
    )


def _openspec_install_model():
    return ToolCallingModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "execute",
                        "args": {
                            "command": "npm install --global @fission-ai/openspec"
                        },
                        "id": "install-openspec-1",
                    }
                ],
            ),
            AIMessage(
                content="OpenSpec installation was rejected and was not completed."
            ),
        ]
    )


def _execute_model(command: str):
    return ToolCallingModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "execute",
                        "args": {"command": command},
                        "id": "execute-1",
                    }
                ],
            ),
            AIMessage(content="command finished"),
        ]
    )


def _chained_approval_model():
    return ToolCallingModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {"file_path": "/first.txt", "content": "first"},
                        "id": "write-first",
                    },
                    {
                        "name": "write_file",
                        "args": {"file_path": "/second.txt", "content": "second"},
                        "id": "write-second",
                    },
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "execute",
                        "args": {"command": "pwd"},
                        "id": "execute-after-writes",
                    }
                ],
            ),
            AIMessage(content="chained approvals completed"),
        ]
    )


def _approval_app(monkeypatch, tmp_path: Path, model):
    from deepagents.backends import LocalShellBackend

    from src import coding_agent

    monkeypatch.setattr(coding_agent, "get_coding_llm", lambda _name: model)
    monkeypatch.setattr(
        coding_agent,
        "CustodianBackend",
        lambda workspace, read_only: LocalShellBackend(
            root_dir=workspace,
            virtual_mode=True,
            env={"PATH": os.environ["PATH"]},
        ),
    )
    monkeypatch.setattr(
        coding_agent,
        "create_custodian_boundary_tools",
        lambda _workspace: [],
    )
    return coding_agent._build_deep_agent(
        tmp_path,
        None,
        execution_mode="approval",
        checkpointer=InMemorySaver(),
    )


def _first_interrupt(app, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    result = asyncio.run(
        app.ainvoke(
            {"messages": [{"role": "user", "content": "write the file"}]},
            config=config,
        )
    )
    assert len(result["__interrupt__"]) == 1
    return config, result["__interrupt__"][0].value


def test_approval_executes_workspace_confined_write(monkeypatch, tmp_path):
    app = _approval_app(monkeypatch, tmp_path, _write_model())
    config, request = _first_interrupt(app, "approve-write")

    assert request["action_requests"][0]["name"] == "write_file"
    asyncio.run(
        app.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    )

    assert (tmp_path / "approved.txt").read_text() == "approved"


def test_edit_decision_is_revalidated_and_writes_edited_action(monkeypatch, tmp_path):
    app = _approval_app(monkeypatch, tmp_path, _write_model())
    config, _request = _first_interrupt(app, "edit-write")

    decision = {
        "type": "edit",
        "edited_action": {
            "name": "write_file",
            "args": {"file_path": "/edited.txt", "content": "edited"},
        },
    }
    asyncio.run(app.ainvoke(Command(resume={"decisions": [decision]}), config=config))

    assert not (tmp_path / "approved.txt").exists()
    assert (tmp_path / "edited.txt").read_text() == "edited"


def test_reject_decision_does_not_write(monkeypatch, tmp_path):
    app = _approval_app(monkeypatch, tmp_path, _write_model())
    config, _request = _first_interrupt(app, "reject-write")

    asyncio.run(
        app.ainvoke(
            Command(
                resume={
                    "decisions": [{"type": "reject", "message": "change not approved"}]
                }
            ),
            config=config,
        )
    )

    assert not (tmp_path / "approved.txt").exists()


def test_documented_execute_tool_requires_approval(monkeypatch, tmp_path):
    app = _approval_app(monkeypatch, tmp_path, _execute_model("pwd"))
    config, request = _first_interrupt(app, "approve-execute")

    assert request["action_requests"][0]["name"] == "execute"
    assert request["action_requests"][0]["args"] == {"command": "pwd"}
    result = asyncio.run(
        app.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    )

    tool_messages = [message for message in result["messages"] if message.type == "tool"]
    assert str(tmp_path.resolve()) in tool_messages[-1].content


def test_documented_execute_tool_accepts_shell_command_syntax(monkeypatch, tmp_path):
    command = "pytest -q && git status --short"
    app = _approval_app(monkeypatch, tmp_path, _execute_model(command))
    _config, request = _first_interrupt(app, "approve-native-command")

    assert request["action_requests"][0]["args"]["command"] == command


def test_edited_action_cannot_escape_workspace(monkeypatch, tmp_path):
    app = _approval_app(monkeypatch, tmp_path, _write_model())
    config, _request = _first_interrupt(app, "reject-escape")
    decision = {
        "type": "edit",
        "edited_action": {
            "name": "write_file",
            "args": {"file_path": "/../escaped.txt", "content": "denied"},
        },
    }

    result = asyncio.run(
        app.ainvoke(Command(resume={"decisions": [decision]}), config=config)
    )

    assert not (tmp_path.parent / "escaped.txt").exists()
    tool_messages = [
        message for message in result["messages"] if message.type == "tool"
    ]
    assert tool_messages[-1].status == "error"


def test_sensitive_and_symlink_escape_paths_are_denied(tmp_path):
    from src.secure_coding_tools import CodingPolicyError, resolve_mutation_path

    with pytest.raises(CodingPolicyError, match="sensitive_path"):
        resolve_mutation_path(tmp_path, "/.env")

    outside = tmp_path.parent / "outside-security-test"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(CodingPolicyError, match="workspace_escape"):
        resolve_mutation_path(tmp_path, "/link/file.txt")


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "echo unsafe"],
        ["git", "reset", "--hard"],
        ["rg", "token", "/etc"],
        ["pytest", "../outside"],
        ["npm", "install", "--prefix", "elsewhere", "unsafe-package"],
        ["pnpm", "add", "--prefix", "elsewhere", "unsafe-package"],
        ["python", "-m", "pip", "install", "--user", "unsafe-package"],
        ["python", "-m", "pip", "install", "--target", "vendor", "unsafe-package"],
        ["ruff", "format", "."],
        ["git", "status", "&&", "whoami"],
        ["git", "diff", "--ext-diff"],
        ["git", "show", "--output=result.txt"],
        ["rg", "--pre", "cat", "pattern"],
        ["openspec", "init"],
        ["openspec", "init", "--tools", "all"],
        ["openspec", "init", "--tools", "codex"],
        ["openspec", "update"],
        ["openspec", "validate"],
    ],
)
def test_command_policy_denies_shell_destructive_and_escape_forms(argv):
    from src.secure_coding_tools import CodingPolicyError, validate_command_argv

    with pytest.raises(CodingPolicyError):
        validate_command_argv(argv)


def test_command_policy_allows_bounded_verification_commands():
    from src.secure_coding_tools import validate_command_argv

    assert validate_command_argv(["git", "status", "--short"])
    assert validate_command_argv(["pytest", "-q", "tests"])
    assert validate_command_argv(["ruff", "format", "--check", "."])
    assert validate_command_argv(["pnpm", "run", "typecheck"])
    assert validate_command_argv(["pwd"])
    assert validate_command_argv(["node", "--version"])


def test_command_policy_allows_approval_gated_workspace_package_installs():
    from src.secure_coding_tools import validate_command_argv

    assert validate_command_argv(["npm", "install", "example-package"])
    assert validate_command_argv(["npm", "install", "--global", "example-cli"])
    assert validate_command_argv(["pnpm", "add", "example-package"])
    assert validate_command_argv(["pnpm", "add", "--global", "example-cli"])
    assert validate_command_argv(["python", "-m", "venv", ".venv"])
    assert validate_command_argv(["python", "-m", "pip", "install", "example-package"])


def test_command_policy_allows_only_bounded_openspec_repository_setup():
    from src.secure_coding_tools import validate_command_argv

    assert validate_command_argv(["openspec", "--version"])
    assert validate_command_argv(["openspec", "init", "--tools", "none"])
    assert validate_command_argv(
        [
            "openspec",
            "init",
            "--tools",
            "none",
            "--profile",
            "core",
        ]
    )
    assert validate_command_argv(["openspec", "validate", "--all"])
    assert validate_command_argv(["openspec", "validate", "--all", "--strict"])


def test_python_package_install_requires_workspace_virtualenv(tmp_path):
    from src.secure_coding_tools import (
        CodingPolicyError,
        _validate_python_install_workspace,
    )

    command = ["python", "-m", "pip", "install", "example-package"]
    with pytest.raises(CodingPolicyError, match="workspace_venv_required"):
        _validate_python_install_workspace(tmp_path, command)

    workspace_python = tmp_path / ".venv" / "bin" / "python"
    workspace_python.parent.mkdir(parents=True)
    workspace_python.touch()
    _validate_python_install_workspace(tmp_path, command)


def test_command_environment_uses_durable_shared_node_tool_paths(tmp_path):
    from src.secure_coding_tools import _command_environment

    environment = _command_environment(tmp_path)
    path_entries = environment["PATH"].split(":")
    assert path_entries[:4] == [
        str(tmp_path / ".venv" / "bin"),
        str(tmp_path / "node_modules" / ".bin"),
        "/opt/coding-tools/node/bin",
        "/opt/coding-tools/pnpm",
    ]
    assert environment["NPM_CONFIG_PREFIX"] == "/opt/coding-tools/node"
    assert environment["PNPM_HOME"] == "/opt/coding-tools/pnpm"


def test_command_path_symlink_escape_is_denied(tmp_path):
    from src.secure_coding_tools import (
        CodingPolicyError,
        _validate_existing_command_paths,
    )

    outside = tmp_path.parent / "outside-command-test"
    outside.mkdir(exist_ok=True)
    (tmp_path / "outside-link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(CodingPolicyError, match="workspace_escape"):
        _validate_existing_command_paths(tmp_path, ["pytest", "outside-link"])


def test_command_output_redacts_credentials():
    from src.secure_coding_tools import redact_command_output

    rendered = redact_command_output(
        "API_KEY=not-for-output\nAuthorization: Bearer abc.def.ghi\n"
    )
    assert "not-for-output" not in rendered
    assert "abc.def.ghi" not in rendered
    assert rendered.count("[REDACTED]") == 2


def test_command_timeout_terminates_process_group(monkeypatch, tmp_path):
    from src import secure_coding_tools

    killed = []

    class Process:
        pid = 4321
        returncode = None

        async def communicate(self):
            await asyncio.sleep(1)

        async def wait(self):
            self.returncode = -9

    async def create_process(*_args, **_kwargs):
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(
        secure_coding_tools.os,
        "killpg",
        lambda pid, sig: killed.append((pid, sig)),
    )

    with pytest.raises(secure_coding_tools.CodingPolicyError, match="command_timeout"):
        asyncio.run(
            secure_coding_tools._run_command(tmp_path, ["git", "status"], timeout=0.001)
        )
    assert killed == [(4321, secure_coding_tools.signal.SIGKILL)]


def test_production_wrapper_surfaces_and_resumes_approval(monkeypatch, tmp_path):
    from src import coding_agent

    nested = _approval_app(monkeypatch, tmp_path, _write_model())

    async def session_agent(*_args):
        return nested

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)

    graph = StateGraph(coding_agent.CodingAgentState)
    graph.add_node("coding", coding_agent.deep_agents_coding_node)
    graph.add_edge(START, "coding")
    app = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "outer-approval"}}
    initial = {
        "messages": [{"role": "user", "content": "write the file"}],
        "workspace": str(tmp_path),
        "execution_mode": "approval",
        "thread_identity": "nested-approval",
    }

    first = asyncio.run(app.ainvoke(initial, config=config))
    assert len(first["__interrupt__"]) == 1
    result = asyncio.run(
        app.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    )

    assert result["coding_status"] == "completed"
    assert (tmp_path / "approved.txt").read_text() == "approved"


def test_outer_coding_handoff_surfaces_openspec_approval_and_returns_directly(
    monkeypatch, tmp_path
):
    from src import chat_ui, coding_agent

    nested = _approval_app(monkeypatch, tmp_path, _openspec_install_model())
    jasper_inputs = []

    async def session_agent(*_args):
        return nested

    async def fake_call_jasper(state):
        jasper_inputs.append(state)
        return {
            "messages": [AIMessage(content=state["messages"][-1]["content"])],
            "visual_artifacts": [],
        }

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    monkeypatch.setattr(chat_ui, "call_jasper", fake_call_jasper)
    app = chat_ui.create_chat_ui().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "outer-openspec-approval"}}
    initial = {
        "messages": [{"role": "user", "content": "Use Coder to install OpenSpec"}],
        "coding_task": "Install OpenSpec in the selected workspace",
        "workspace": str(tmp_path),
        "target_agent": "coding",
        "execution_mode": "approval",
    }

    first = asyncio.run(app.ainvoke(initial, config=config))
    request = first["__interrupt__"][0].value

    assert request["action_requests"][0]["name"] == "execute"
    assert request["action_requests"][0]["args"]["command"] == (
        "npm install --global @fission-ai/openspec"
    )

    result = asyncio.run(
        app.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {"type": "reject", "message": "Do not install it yet."}
                    ]
                }
            ),
            config=config,
        )
    )

    assert jasper_inputs == []
    assert result["messages"][-1]["name"] == "coding"
    content = result["messages"][-1]["content"]
    assert content.startswith("Completion report")
    assert "OpenSpec installation was rejected and was not completed." in content
    assert "command runtime: native_custodian_host" in content
    assert f"selected repository: {tmp_path}" in content
    assert result["coding_status"] == "completed"


def test_native_wrapper_resumes_ordered_chained_approval_batches(
    monkeypatch, tmp_path
):
    from src import coding_agent

    nested = _approval_app(monkeypatch, tmp_path, _chained_approval_model())

    async def session_agent(*_args):
        return nested

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    graph = StateGraph(coding_agent.CodingAgentState)
    graph.add_node("coding", coding_agent.deep_agents_coding_node)
    graph.add_edge(START, "coding")
    app = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "outer-chained-approvals"}}
    initial = {
        "messages": [{"role": "user", "content": "complete the chained work"}],
        "workspace": str(tmp_path),
        "execution_mode": "approval",
        "thread_identity": "nested-chained-approvals",
    }

    first = asyncio.run(app.ainvoke(initial, config=config))
    assert len(first["__interrupt__"][0].value["action_requests"]) == 2

    second = asyncio.run(
        app.ainvoke(
            Command(
                resume={
                    "decisions": [{"type": "approve"}, {"type": "approve"}]
                }
            ),
            config=config,
        )
    )
    assert len(second["__interrupt__"][0].value["action_requests"]) == 1

    result = asyncio.run(
        app.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    )
    assert result["coding_status"] == "completed"
    assert (tmp_path / "first.txt").read_text() == "first"
    assert (tmp_path / "second.txt").read_text() == "second"


def test_coding_node_propagates_cancellation(monkeypatch, tmp_path):
    from src import coding_agent

    class SlowApp:
        async def aget_state(self, _config):
            return type("Snapshot", (), {"values": {}, "tasks": ()})()

        async def ainvoke(self, _payload, config=None):
            await asyncio.sleep(10)

    async def session_agent(*_args):
        return SlowApp()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)

    async def cancel():
        task = asyncio.create_task(
            coding_agent.deep_agents_coding_node(
                {
                    "messages": [{"role": "user", "content": "wait"}],
                    "workspace": str(tmp_path),
                    "thread_identity": "cancel-thread",
                }
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())


def test_coding_node_ignores_removed_whole_run_timeout_setting(monkeypatch, tmp_path):
    from src import coding_agent

    class SlowApp:
        async def ainvoke(self, payload, config=None):
            await asyncio.sleep(0.01)
            return {
                "messages": [
                    *payload["messages"],
                    AIMessage(content="Finished after the former cutoff."),
                ]
            }

    monkeypatch.setenv("CODING_AGENT_TIMEOUT_SECONDS", "0")

    async def session_agent(*_args):
        return SlowApp()

    monkeypatch.setattr(coding_agent, "_session_agent", session_agent)
    result = asyncio.run(
        coding_agent.deep_agents_coding_node(
            {
                "messages": [{"role": "user", "content": "wait"}],
                "workspace": str(tmp_path),
                "thread_identity": "timeout-thread",
            }
        )
    )

    assert result["coding_status"] == "completed"
    assert "Completion report" in result["messages"][0].content
