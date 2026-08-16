"""Canonical workspace and execution-boundary policy shared by backend agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, TypedDict


class WorkspacePolicyError(ValueError):
    """Raised when a selected workspace cannot be used without substitution."""


class ExecutionManifest(TypedDict):
    """Server-attested identity for repository files and command execution."""

    filesystem_origin: Literal["macos_host_bind_mount"]
    selected_repository: str
    command_runtime: Literal["linux_agent_server_container"]
    native_host_operations: Literal["unavailable_without_separate_approval"]
    host_operation_request: Literal["available", "unavailable"]
    docker_broker_request: Literal["available", "unavailable"]


# These are the host-path-preserving bind-mount roots supported by the macOS
# deployment. Operators can narrow or replace them with WORKSPACE_AUTHORIZED_ROOTS.
_DEFAULT_AUTHORIZED_ROOTS = (Path("/Users"), Path("/Volumes/Storage"))


def authorized_workspace_roots() -> tuple[Path, ...]:
    """Return canonical, existing roots explicitly authorized by the server."""

    configured = os.getenv("WORKSPACE_AUTHORIZED_ROOTS")
    raw_roots = (
        [Path(value) for value in configured.split(os.pathsep) if value]
        if configured is not None
        else list(_DEFAULT_AUTHORIZED_ROOTS)
    )
    roots: list[Path] = []
    for raw_root in raw_roots:
        if not raw_root.is_absolute():
            continue
        try:
            root = raw_root.resolve(strict=True)
        except OSError:
            continue
        if root.is_dir() and root not in roots:
            roots.append(root)
    return tuple(roots)


def canonical_workspace(raw_workspace: str | os.PathLike[str] | None) -> Path:
    """Validate one exact selected directory, without selecting any fallback."""

    if raw_workspace is None or not str(raw_workspace).strip():
        raise WorkspacePolicyError("workspace is required")
    candidate = Path(raw_workspace).expanduser()
    if not candidate.is_absolute():
        raise WorkspacePolicyError("workspace must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise WorkspacePolicyError("workspace does not exist") from exc
    if not resolved.is_dir():
        raise WorkspacePolicyError("workspace must be a directory")

    roots = authorized_workspace_roots()
    if not roots or not any(resolved.is_relative_to(root) for root in roots):
        raise WorkspacePolicyError("workspace is outside authorized roots")
    return resolved


def host_operation_request_available() -> bool:
    """Report availability only when all non-secret operator inputs validate."""

    # Lazy import keeps workspace validation independent from optional tool loading.
    from src.macos_host_operations import host_operation_request_available as available

    return available()


def docker_broker_request_available() -> bool:
    """Report Docker broker availability only for a validated fixed endpoint."""

    from src.docker_broker_operations import (
        docker_broker_request_available as available,
    )

    return available()


def execution_manifest(workspace: Path) -> ExecutionManifest:
    """Produce deployment truth; never accept runtime identity from model state."""

    canonical = canonical_workspace(workspace)
    return {
        "filesystem_origin": "macos_host_bind_mount",
        "selected_repository": str(canonical),
        "command_runtime": "linux_agent_server_container",
        "native_host_operations": "unavailable_without_separate_approval",
        "host_operation_request": (
            "available" if host_operation_request_available() else "unavailable"
        ),
        "docker_broker_request": (
            "available" if docker_broker_request_available() else "unavailable"
        ),
    }


def format_execution_manifest(manifest: ExecutionManifest) -> str:
    """Return stable prompt/result text for the server-produced manifest."""

    return "\n".join(
        (
            "Execution manifest (server-produced):",
            f"- filesystem origin: {manifest['filesystem_origin']}",
            f"- selected repository: {manifest['selected_repository']}",
            f"- command runtime: {manifest['command_runtime']}",
            f"- native host operations: {manifest['native_host_operations']}",
            f"- request_macos_host_operation: {manifest['host_operation_request']}",
            f"- request_docker_compose_operation: {manifest['docker_broker_request']}",
        )
    )
