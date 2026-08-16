from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
import yaml
from docker_broker.audit import AuditLog
from docker_broker.config import Settings
from docker_broker.models import ComposeTarget
from docker_broker.policy import ComposePolicy
from docker_broker.runner import DockerRunner

_DOCKER = Path("/usr/local/bin/docker")


@pytest.mark.asyncio
@pytest.mark.skipif(not _DOCKER.exists(), reason="Docker CLI is unavailable")
async def test_real_compose_canonicalization(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    await asyncio.to_thread(
        subprocess.run,
        ["/usr/bin/git", "init", "--quiet", str(repository)],
        check=True,
    )
    stack = repository / "stack"
    stack.mkdir()
    (stack / "compose.yaml").write_text(
        yaml.safe_dump(
            {
                "services": {
                    "web": {
                        "image": "busybox@sha256:" + "0" * 64,
                        "ports": ["127.0.0.1:18080:8080"],
                        "volumes": ["data:/data"],
                        "restart": "no",
                    },
                    "debug": {
                        "image": "busybox@sha256:" + "1" * 64,
                        "profiles": ["debug"],
                    },
                },
                "volumes": {"data": {}},
            },
            sort_keys=False,
        )
    )
    state = tmp_path / "state"
    settings = Settings.from_values(
        allowed_roots=[str(repository.resolve())],
        state_directory=str(state),
        agent_server_url="http://127.0.0.1:8123",
        owner_id="owner-one",
        docker_path=str(_DOCKER),
    )
    project = ComposePolicy(settings).validate(
        repository.resolve(),
        ComposeTarget(project_directory="stack", compose_files=["compose.yaml"]),
    )
    runner = DockerRunner(settings, AuditLog(state / "audit.jsonl"))
    await runner.validate_config(project)
    assert not list(state.glob("operation-*"))
