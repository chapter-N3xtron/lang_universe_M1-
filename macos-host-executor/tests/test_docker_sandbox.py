from __future__ import annotations

import hashlib
import json
import shlex
import threading
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from macos_host_executor.adapters import DockerSandboxAdapter
from macos_host_executor.errors import PolicyDeniedError
from macos_host_executor.models import (
    DockerSandboxAction,
    HostAction,
    HostOperationPlan,
)
from macos_host_executor.policy import ActionPolicy, ExecutionPlan, PolicyConfig
from macos_host_executor.runner import RunResult


def action(workspace: Path, **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "category": "docker_sandbox",
        "workspace": str(workspace),
        "project_directory": "project dir",
        "compose_file": "compose file.yaml",
        "compose_sha256": hashlib.sha256(b"services: {}\n").hexdigest(),
        "operation": "up",
        "services": ["web"],
        "profiles": ["dev"],
    }
    value.update(updates)
    return value


def operation(workspace: Path, **action_updates: object) -> HostOperationPlan:
    action_value = action(workspace, **action_updates)
    mutation = []
    if action_value["operation"] != "ps":
        mutation = [
            {
                "operation": "replace",
                "path": str(workspace.resolve()),
                "detail": "Compose may replace workspace runtime state",
            }
        ]
    return HostOperationPlan.model_validate_json(
        json.dumps(
            {
                "action": action_value,
                "expected_mutations": mutation,
                "timeout_seconds": 60,
                "rollback": {
                    "strategy": "none",
                    "removes_only_request_created_paths": True,
                    "may_require_human_inspection": action_value["operation"] != "ps",
                },
                "expiry_seconds": 300,
            }
        )
    )


def configured(workspace: Path, sbx: Path) -> ActionPolicy:
    return ActionPolicy(
        PolicyConfig(
            sandbox_workspace_roots=(str(workspace.parent),),
            sbx_executable=str(sbx),
            sbx_home=str(workspace.parent),
        )
    )


def prepare(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "repo with spaces"
    project = workspace / "project dir"
    project.mkdir(parents=True)
    (project / "compose file.yaml").write_text("services: {}\n")
    sbx = tmp_path / "sbx"
    sbx.write_text("#!/bin/sh\n")
    sbx.chmod(0o700)
    return workspace, sbx


def test_schema_rejects_raw_authority_and_invalid_paths(tmp_path: Path) -> None:
    workspace, _ = prepare(tmp_path)
    adapter = TypeAdapter(HostAction)
    valid = action(workspace)
    for field, value in (
        ("command", "docker compose logs"),
        ("name", "caller-name"),
        ("environment", {"TOKEN": "secret"}),
        ("argv", ["docker", "ps"]),
        ("executable", "/tmp/sbx"),
    ):
        with pytest.raises(ValidationError):
            adapter.validate_json(json.dumps({**valid, field: value}))
    for field, value in (
        ("project_directory", "/absolute"),
        ("project_directory", "../escape"),
        ("compose_file", "dir\\compose.yaml"),
        ("compose_file", "bad\x00name"),
    ):
        with pytest.raises(ValidationError):
            adapter.validate_json(json.dumps({**valid, field: value}))
    with pytest.raises(ValidationError, match="down does not accept services"):
        adapter.validate_json(json.dumps({**valid, "operation": "down"}))


def test_policy_derives_name_paths_and_quoted_fixed_argv(tmp_path: Path) -> None:
    workspace, sbx = prepare(tmp_path)
    plan = configured(workspace, sbx).plan(operation(workspace))
    digest = hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()[:12]
    assert plan.executable == str(sbx.resolve())
    assert plan.argv[:4] == (str(sbx.resolve()), "run", "shell", "--name")
    assert plan.argv[4] == f"repo-with-spaces-{digest}"
    assert plan.argv[5:8] == (str(workspace.resolve()), "--", "-c")
    expected_compose = (
        "docker",
        "compose",
        "--project-directory",
        str((workspace / "project dir").resolve()),
        "--file",
        str((workspace / "project dir" / "compose file.yaml").resolve()),
        "--profile",
        "dev",
        "up",
        "--detach",
        "web",
    )
    assert plan.argv[8] == shlex.join(expected_compose)
    assert shlex.split(plan.argv[8]) == list(expected_compose)

    (workspace / "project dir" / "compose file.yaml").write_text(
        "services:\n  web: {}\n"
    )
    with pytest.raises(PolicyDeniedError, match="hash"):
        configured(workspace, sbx).revalidate(operation(workspace))


def test_policy_defaults_and_mutation_contract_fail_closed(tmp_path: Path) -> None:
    workspace, sbx = prepare(tmp_path)
    with pytest.raises(PolicyDeniedError, match="SBX executable"):
        ActionPolicy(PolicyConfig()).plan(operation(workspace))
    with pytest.raises(PolicyDeniedError, match="operator home"):
        ActionPolicy(
            PolicyConfig(
                sandbox_workspace_roots=(str(workspace.parent),),
                sbx_executable=str(sbx),
            )
        ).plan(operation(workspace))
    policy = configured(workspace, sbx)
    data = operation(workspace).model_dump(mode="json")
    data["expected_mutations"] = []
    with pytest.raises(PolicyDeniedError, match="exactly one"):
        policy.plan(HostOperationPlan.model_validate_json(json.dumps(data)))
    ps = policy.plan(operation(workspace, operation="ps", services=[]))
    assert ps.approved_paths[0] == str(workspace.resolve())


class Runner:
    def __init__(self) -> None:
        self.argv: tuple[str, ...] | None = None

    def run(self, argv, **_kwargs):  # type: ignore[no-untyped-def]
        self.argv = argv
        return RunResult(
            exit_code=0,
            stdout="TOKEN=must-not-leak",
            stderr="secret failure detail",
            output_truncated=True,
            timed_out=False,
            cancelled=False,
            pid=42,
        )


def test_adapter_suppresses_all_process_output() -> None:
    runner = Runner()
    adapter = DockerSandboxAdapter(runner)  # type: ignore[arg-type]
    action_model = DockerSandboxAction.model_validate(
        {
            "category": "docker_sandbox",
            "workspace": "/tmp/repo",
            "project_directory": ".",
            "compose_file": "compose.yaml",
            "compose_sha256": "0" * 64,
            "operation": "up",
            "services": (),
            "profiles": (),
        }
    )
    plan = ExecutionPlan(
        category="docker_sandbox",
        executable="/usr/local/bin/sbx",
        argv=("/usr/local/bin/sbx", "run"),
        approved_paths=("/tmp/repo", "/tmp/repo", "/tmp/repo/compose.yaml"),
    )
    result = adapter.execute(
        action_model,
        plan,
        timeout=10,
        output_limit=4096,
        cancel=threading.Event(),
    )
    assert runner.argv == plan.argv
    assert result.success and result.verified
    assert result.process.stdout == result.process.stderr == ""
    assert result.process.exit_code == 0 and result.process.output_truncated
    assert "secret" not in result.message.lower()
