from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from docker_broker.api import create_app
from docker_broker.audit import AuditLog
from docker_broker.config import Settings
from docker_broker.confirmation import NativeConfirmation
from docker_broker.errors import ConflictError, OperationError, PolicyError
from docker_broker.leases import Lease
from docker_broker.models import ComposeApplyRequest, ComposeTarget
from docker_broker.policy import ComposePolicy
from docker_broker.runner import DockerRunner
from httpx import ASGITransport, AsyncClient


def write_project(repository: Path) -> Path:
    directory = repository / "stack"
    directory.mkdir(exist_ok=True)
    compose = directory / "compose.yaml"
    compose.write_text(
        yaml.safe_dump({"services": {"web": {"image": "busybox@sha256:" + "0" * 64}}})
    )
    return compose


def executable(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body)
    os.chmod(path, 0o700)
    return path


def config_script(captured: Path | None = None) -> str:
    capture = (
        f" pathlib.Path({str(captured)!r}).write_text(files[0].read_text())\n"
        if captured
        else ""
    )
    return (
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "def merge(left, right):\n"
        " for key, value in right.items():\n"
        "  if isinstance(value, dict) and isinstance(left.get(key), dict): merge(left[key], value)\n"
        "  else: left[key] = value\n"
        "if 'config' in args:\n"
        " files = [pathlib.Path(args[index + 1]) for index, item in enumerate(args) if item == '--file']\n"
        " model = {}\n"
        " for path in files: merge(model, json.loads(path.read_text()))\n"
        f"{capture}"
        " for service in model['services'].values():\n"
        "  service['mem_limit'] = 2 * 1024**3\n"
        "  service['cpus'] = 2.0\n"
        "  service['pids_limit'] = 512\n"
        " print(json.dumps(model))\n"
        " sys.exit(0)\n"
    )


def validated(settings, repository: Path):  # type: ignore[no-untyped-def]
    return ComposePolicy(settings).validate(
        repository,
        ComposeTarget(project_directory="stack", compose_files=["compose.yaml"]),
    )


def lease(repository: Path) -> Lease:
    return Lease(
        token_digest="token-digest",
        session_id="thread-one",
        owner_id="owner-one",
        workspace=repository,
        scope_digest="scope-digest",
        expires_monotonic=time.monotonic() + 300,
        expires_at=datetime.now(UTC),
        revoked=asyncio.Event(),
    )


def apply_request(request_id: str) -> ComposeApplyRequest:
    return ComposeApplyRequest(
        request_id=request_id,
        project_directory="stack",
        compose_files=["compose.yaml"],
        operation="up",
        services=[],
        profiles=[],
    )


@pytest.mark.asyncio
async def test_compose_execution_uses_validated_snapshot(
    settings, repository, tmp_path
):
    compose = write_project(repository)
    captured = tmp_path / "captured.yaml"
    docker = executable(
        tmp_path / "snapshot-docker",
        config_script(captured),
    )
    hardened = replace(settings, docker_path=docker)
    project = validated(hardened, repository)
    compose.write_text("services:\n  web:\n    image: busybox\n    privileged: true\n")
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    await runner.validate_config(project)
    assert "privileged" not in captured.read_text()
    assert "busybox@sha256:" in captured.read_text()
    assert not list(hardened.state_directory.glob("operation-*"))


@pytest.mark.asyncio
async def test_snapshot_rejects_symlinks(settings, repository):
    write_project(repository)
    (repository / "stack" / "escape").symlink_to("/etc/passwd")
    project = validated(settings, repository)
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    with pytest.raises(PolicyError, match="symlinks"):
        await runner.validate_config(project)


@pytest.mark.asyncio
async def test_snapshot_size_is_bounded(settings, repository):
    write_project(repository)
    (repository / "stack" / "large.bin").write_bytes(b"x" * 100)
    hardened = replace(settings, max_snapshot_bytes=50)
    project = validated(hardened, repository)
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    with pytest.raises(PolicyError, match="snapshot exceeds"):
        await runner.validate_config(project)


async def wait_for_pid(path: Path) -> int:
    for _ in range(100):
        if path.exists():
            return int(path.read_text())
        await asyncio.sleep(0.02)
    raise AssertionError("Docker test process did not start")


def sleeping_docker(tmp_path: Path, name: str) -> tuple[Path, Path]:
    pid_file = tmp_path / f"{name}.pid"
    docker = executable(
        tmp_path / name,
        config_script()
        + "import os, time\n"
        + f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        + "time.sleep(30)\n",
    )
    return docker, pid_file


def assert_process_gone(pid: int) -> None:
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_revocation_kills_running_process_group(settings, repository, tmp_path):
    write_project(repository)
    docker, pid_file = sleeping_docker(tmp_path, "revoke-docker")
    hardened = replace(settings, docker_path=docker)
    project = validated(hardened, repository)
    authority = lease(repository)
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    task = asyncio.create_task(
        runner.apply(project, apply_request("request-revoke"), authority)
    )
    pid = await wait_for_pid(pid_file)
    authority.revoked.set()
    with pytest.raises(OperationError, match="revoked"):
        await asyncio.wait_for(task, timeout=2)
    assert_process_gone(pid)


@pytest.mark.asyncio
async def test_cancellation_kills_running_process_group(settings, repository, tmp_path):
    write_project(repository)
    docker, pid_file = sleeping_docker(tmp_path, "cancel-docker")
    hardened = replace(settings, docker_path=docker)
    project = validated(hardened, repository)
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    task = asyncio.create_task(
        runner.apply(project, apply_request("request-cancel"), lease(repository))
    )
    pid = await wait_for_pid(pid_file)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert_process_gone(pid)


def test_app_rejects_missing_client_authentication(settings):
    with pytest.raises(ValueError, match="authentication"):
        create_app(replace(settings, client_secret=None))


def test_allow_builds_requires_trusted_buildx_plugin(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    state = tmp_path / "state"
    docker = tmp_path / "bin" / "docker"
    docker.parent.mkdir()
    docker.write_text("docker")
    plugins = tmp_path / "cli-plugins"
    plugins.mkdir()
    (plugins / "docker-compose").write_text("compose")

    monkeypatch.setattr(
        Settings,
        "_trusted_executable",
        staticmethod(lambda path, _roots, _name: path.resolve()),
    )
    with pytest.raises(ValueError, match="trusted Docker Buildx plugin"):
        Settings.from_values(
            allowed_roots=[str(repository)],
            state_directory=str(state),
            agent_server_url="http://127.0.0.1:8123",
            owner_id="owner-one",
            docker_path=str(docker),
            allow_builds=True,
        )


@pytest.mark.asyncio
async def test_client_auth_body_limit_and_validation_redaction(settings):
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        denied = await client.get("/v1/health")
        assert denied.status_code == 401
        headers = {"X-Broker-Client-Secret": settings.client_secret or ""}
        invalid = await client.post(
            "/v1/sessions/activate",
            headers=headers,
            json={
                "session_id": "thread-one",
                "owner_id": "owner-one",
                "workspace": "top-secret-value",
                "lease_seconds": "top-secret-value",
            },
        )
        assert invalid.status_code == 422
        assert "top-secret-value" not in invalid.text
        oversized = await client.post(
            "/v1/sessions/activate",
            headers={**headers, "Content-Type": "application/json"},
            content=b"x" * 70_000,
        )
        assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_build_image_is_rewritten_and_builder_is_ephemeral(
    settings, repository, fake_docker
):
    directory = repository / "stack"
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM busybox\n")
    (directory / "compose.yaml").write_text(
        yaml.safe_dump(
            {
                "services": {
                    "web": {
                        "build": ".",
                        "image": "jasper-langgraph:current",
                    }
                }
            }
        )
    )
    project = validated(settings, repository)
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    snapshot = await asyncio.to_thread(runner._snapshot, project)
    try:
        model = json.loads(snapshot.compose_file.read_text())
        image = model["services"]["web"]["image"]
        assert image.startswith("jasper-broker-managed/")
        assert image != "jasper-langgraph:current"
    finally:
        await asyncio.to_thread(runner._remove_snapshot, snapshot)
    request = ComposeApplyRequest(
        request_id="request-build",
        project_directory="stack",
        compose_files=["compose.yaml"],
        operation="build",
        services=[],
        profiles=[],
    )
    response = await runner.apply(project, request, lease(repository))
    assert response["status"] == "succeeded"
    _, log = fake_docker
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(command[:2] == ["buildx", "create"] for command in commands)
    assert any(command[:2] == ["buildx", "bake"] for command in commands)
    assert any(command[:2] == ["buildx", "rm"] for command in commands)


@pytest.mark.asyncio
async def test_empty_env_and_canonical_execution_prevent_env_drift(
    settings, repository
):
    compose = write_project(repository)
    model = yaml.safe_load(compose.read_text())
    model["services"]["web"]["environment"] = {"TOKEN": "${TOKEN:-repository-secret}"}
    compose.write_text(yaml.safe_dump(model))
    (repository / "stack" / ".env").write_text(
        "TOKEN=repository-secret\nCOMPOSE_REMOVE_ORPHANS=1\n"
    )
    project = validated(settings, repository)
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    snapshot = await asyncio.to_thread(runner._snapshot, project)
    try:
        await runner._validate_snapshot(project, snapshot)
        effective = json.loads(snapshot.execution_file.read_text())
        assert snapshot.empty_env_file.read_text() == ""
        assert runner._environment["COMPOSE_DISABLE_ENV_FILE"] == "1"
        assert runner._environment["COMPOSE_REMOVE_ORPHANS"] == "0"
        assert effective["services"]["web"]["environment"]["TOKEN"].startswith("$$")
    finally:
        await asyncio.to_thread(runner._remove_snapshot, snapshot)


@pytest.mark.asyncio
async def test_idempotency_is_durable_and_binds_snapshot(
    settings, repository, fake_docker
):
    write_project(repository)
    project = validated(settings, repository)
    authority = lease(repository)
    request = apply_request("request-durable")
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    first = await runner.apply(project, request, authority)
    renewed = lease(repository)
    object.__setattr__(renewed, "token_digest", "different-token")
    restarted_runner = DockerRunner(
        settings, AuditLog(settings.state_directory / "audit.jsonl")
    )
    second = await restarted_runner.apply(project, request, renewed)
    assert first == second
    _, log = fake_docker
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert sum("up" in command for command in commands) == 1
    (repository / "stack" / "new-input.txt").write_text("changed")
    with pytest.raises(ConflictError, match="different operation inputs"):
        await restarted_runner.apply(project, request, renewed)


@pytest.mark.asyncio
async def test_revoke_kills_descendant_after_group_leader_exits(settings, tmp_path):
    child_pid_file = tmp_path / "descendant.pid"
    docker = executable(
        tmp_path / "forking-docker",
        "import os, pathlib, time\n"
        "child = os.fork()\n"
        "if child: os._exit(0)\n"
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n",
    )
    hardened = replace(settings, docker_path=docker)
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    revoked = asyncio.Event()
    operation = asyncio.create_task(
        runner._run(
            [str(docker), "test"],
            timeout=10,
            capture=True,
            revoke_event=revoked,
        )
    )
    child_pid = await wait_for_pid(child_pid_file)
    revoked.set()
    with pytest.raises(OperationError, match="revoked"):
        await operation
    for _ in range(100):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.02)
    else:
        raise AssertionError("descendant process survived revocation")


@pytest.mark.asyncio
async def test_snapshot_cancellation_waits_for_copy_and_cleans_state(
    settings, repository, monkeypatch
):
    write_project(repository)
    project = validated(settings, repository)
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    original_snapshot = runner._snapshot

    def delayed_snapshot(value):
        time.sleep(0.1)
        return original_snapshot(value)

    monkeypatch.setattr(runner, "_snapshot", delayed_snapshot)
    operation = asyncio.create_task(runner._create_snapshot(project))
    await asyncio.sleep(0.01)
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert not list(settings.state_directory.glob("operation-*"))
    await runner.close()


@pytest.mark.asyncio
async def test_runner_close_removes_private_docker_config(settings):
    runner = DockerRunner(settings, AuditLog(settings.state_directory / "audit.jsonl"))
    assert len(list(settings.state_directory.glob("docker-config-*"))) == 1
    await runner.close()
    await runner.close()
    assert not list(settings.state_directory.glob("docker-config-*"))


@pytest.mark.asyncio
async def test_canonical_model_is_revalidated_against_policy(
    settings, repository, tmp_path
):
    write_project(repository)
    malicious = executable(
        tmp_path / "malicious-compose",
        "import json, sys\n"
        "if 'config' in sys.argv:\n"
        " print(json.dumps({'services': {'web': "
        "{'image': 'busybox@sha256:' + '0' * 64, 'privileged': True}}}))\n",
    )
    hardened = replace(settings, docker_path=malicious)
    project = validated(hardened, repository)
    runner = DockerRunner(hardened, AuditLog(hardened.state_directory / "audit.jsonl"))
    with pytest.raises(PolicyError, match="forbidden authority"):
        await runner.validate_config(project)
    await runner.close()


@pytest.mark.asyncio
async def test_native_approval_states_that_builds_are_blocked(repository, tmp_path):
    arguments = tmp_path / "dialog-arguments.json"
    osascript = executable(
        tmp_path / "fake-osascript",
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(arguments)!r}).write_text(json.dumps(sys.argv))\n"
        "print('button returned:Allow')\n",
    )
    confirmation = NativeConfirmation(osascript)
    await confirmation.approve(
        session_id="thread-one",
        owner_id="owner-one",
        workspace=repository,
        lease_seconds=300,
    )
    message = json.loads(arguments.read_text())[-1]
    assert "builds are blocked" in message
    assert "pull, build" not in message
