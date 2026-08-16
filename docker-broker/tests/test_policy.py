from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from docker_broker.errors import PolicyError
from docker_broker.models import ComposeTarget
from docker_broker.policy import ComposePolicy
from pydantic import ValidationError


def write_compose(repository: Path, value: dict) -> Path:
    project = repository / "infrastructure" / "sample"
    project.mkdir(parents=True, exist_ok=True)
    (project / "Dockerfile").write_text("FROM busybox:1.36\n")
    compose = project / "compose.yaml"
    compose.write_text(yaml.safe_dump(value, sort_keys=False))
    return compose


def safe_project() -> dict:
    return {
        "services": {
            "web": {
                "build": ".",
                "ports": ["127.0.0.1:18080:8080"],
                "volumes": ["data:/data"],
                "environment": {"PLANE_TOKEN": "${PLANE_TOKEN}"},
            }
        },
        "volumes": {"data": {}},
    }


def validate(policy: ComposePolicy, repository: Path) -> None:
    policy.validate(
        repository,
        ComposeTarget(
            project_directory="infrastructure/sample",
            compose_files=["compose.yaml"],
        ),
    )


def test_allows_nested_repository_project(settings, repository):
    write_compose(repository, safe_project())
    project = ComposePolicy(settings).validate(
        repository,
        ComposeTarget(
            project_directory="infrastructure/sample",
            compose_files=["compose.yaml"],
        ),
    )
    assert project.project_name.startswith("jasper-sample-")
    assert project.service_names == ("web",)
    assert project.override["services"]["web"]["pids_limit"] == 512


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["services"]["web"].update(privileged=True),
        lambda value: value["services"]["web"].update(devices=["/dev/disk0"]),
        lambda value: value["services"]["web"].update(cap_add=["SYS_ADMIN"]),
        lambda value: value["services"]["web"].update(network_mode="host"),
        lambda value: value["services"]["web"].update(ports=["0.0.0.0:18080:8080"]),
        lambda value: value["services"]["web"].update(
            volumes=["/var/run/docker.sock:/var/run/docker.sock"]
        ),
        lambda value: value.update(networks={"shared": {"external": True}}),
        lambda value: value.update(networks={"shared": {"driver": "macvlan"}}),
        lambda value: value.update(
            volumes={
                "data": {
                    "driver": "local",
                    "driver_opts": {"type": "none", "device": "/", "o": "bind"},
                }
            }
        ),
        lambda value: value["services"]["web"].update(deploy={"replicas": 1000}),
        lambda value: value["services"]["web"].update(extends={"service": "base"}),
        lambda value: value["services"]["web"].update(env_file=".env"),
        lambda value: value["services"]["web"].update(pid="host"),
        lambda value: value["services"]["web"].update(
            build={"context": ".", "cache_to": ["type=local,dest=/tmp/cache"]}
        ),
        lambda value: value.update(configs={"host": {"file": "/etc/passwd"}}),
    ],
)
def test_rejects_escape_and_credential_features(settings, repository, mutate):
    value = safe_project()
    mutate(value)
    write_compose(repository, value)
    with pytest.raises(PolicyError):
        validate(ComposePolicy(settings), repository)


def test_rejects_project_path_escape(settings, repository, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "compose.yaml").write_text("services: {web: {image: busybox}}\n")
    with pytest.raises(PolicyError):
        ComposePolicy(settings).validate(
            repository,
            ComposeTarget(
                project_directory="../outside", compose_files=["compose.yaml"]
            ),
        )


def test_workspace_must_be_git_root(settings, repository):
    child = repository / "child"
    child.mkdir()
    with pytest.raises(PolicyError, match="repository root"):
        ComposePolicy(settings).resolve_workspace(str(child))


def test_rejects_yaml_aliases(settings, repository):
    project = repository / "infrastructure" / "sample"
    project.mkdir(parents=True)
    (project / "compose.yaml").write_text(
        "services:\n  base: &base\n    image: busybox\n  web:\n    <<: *base\n"
    )
    with pytest.raises(PolicyError, match="aliases and anchors"):
        validate(ComposePolicy(settings), repository)


def test_rejects_multiple_compose_files():
    with pytest.raises(ValidationError):
        ComposeTarget(
            project_directory="stack",
            compose_files=["compose.yaml", "compose.override.yaml"],
        )


def test_rejects_absolute_build_context(settings, repository):
    value = safe_project()
    value["services"]["web"]["build"] = "/tmp"
    write_compose(repository, value)
    with pytest.raises(PolicyError, match="relative"):
        validate(ComposePolicy(settings), repository)


def test_safe_default_rejects_builds(settings, repository):
    write_compose(repository, safe_project())
    with pytest.raises(PolicyError, match="builds are disabled"):
        validate(ComposePolicy(replace(settings, allow_builds=False)), repository)


def test_image_only_service_requires_digest(settings, repository):
    write_compose(
        repository,
        {"services": {"web": {"image": "jasper-langgraph:current"}}},
    )
    with pytest.raises(PolicyError, match="digest"):
        validate(ComposePolicy(settings), repository)


def test_yaml_12_preserves_unquoted_no(settings, repository):
    project = repository / "infrastructure" / "sample"
    project.mkdir(parents=True)
    (project / "Dockerfile").write_text("FROM busybox\n")
    (project / "compose.yaml").write_text(
        "services:\n  web:\n    build: .\n    restart: no\n"
    )
    result = ComposePolicy(settings).validate(
        repository,
        ComposeTarget(
            project_directory="infrastructure/sample",
            compose_files=["compose.yaml"],
        ),
    )
    assert result.compose_document["services"]["web"]["restart"] == "no"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("shm_size", "2g"),
        ("stop_grace_period", "10m"),
        ("healthcheck", {"test": ["CMD", "true"], "retries": 1000}),
        ("labels", ["${LABEL_NAME}=unsafe"]),
    ],
)
def test_rejects_unbounded_or_interpolated_controls(settings, repository, key, value):
    compose = safe_project()
    compose["services"]["web"][key] = value
    write_compose(repository, compose)
    with pytest.raises(PolicyError):
        validate(ComposePolicy(settings), repository)
