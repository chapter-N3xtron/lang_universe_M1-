"""Host-workspace identity policy for the native Custodian boundary."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal, TypedDict


class WorkspacePolicyError(ValueError):
    """Raised when a selected workspace cannot be used without substitution."""


class ExecutionManifest(TypedDict):
    """Server-attested identity for repository files and command execution."""

    filesystem_origin: Literal["native_custodian"]
    selected_repository: str
    command_runtime: Literal["native_custodian_host"]
    host_worker: Literal["available", "unavailable"]


_DEFAULT_AUTHORIZED_ROOTS = (Path("/Users"), Path("/Volumes/Storage"))


def _lexical_absolute(path: Path) -> Path:
    """Normalize an absolute host path without requiring it in this container."""

    return Path(os.path.normpath(str(path)))


def authorized_workspace_roots() -> tuple[Path, ...]:
    """Return configured host roots without probing the Agent Server filesystem."""

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
        root = _lexical_absolute(raw_root)
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def canonical_workspace(raw_workspace: str | os.PathLike[str] | None) -> Path:
    """Validate one exact absolute host directory name, without local I/O/fallback."""

    if raw_workspace is None or not str(raw_workspace).strip():
        raise WorkspacePolicyError("workspace is required")
    candidate = Path(str(raw_workspace))
    if not candidate.is_absolute():
        raise WorkspacePolicyError("workspace must be absolute")
    normalized = _lexical_absolute(candidate)
    # Reject aliases rather than silently changing the selected repository identity.
    if str(normalized) != str(candidate):
        raise WorkspacePolicyError("workspace must be a canonical absolute host path")
    roots = authorized_workspace_roots()
    if not roots or not any(
        normalized == root or normalized.is_relative_to(root) for root in roots
    ):
        raise WorkspacePolicyError("workspace is outside authorized roots")
    return normalized


def host_worker_available() -> bool:
    """Report whether the configured native Custodian worker is healthy."""
    base_url = os.getenv(
        "CUSTODIAN_WORKER_URL", "http://host.docker.internal:8765"
    ).strip()
    if not base_url:
        return False
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=1.0) as response:
            payload = json.loads(response.read(4096).decode("utf-8"))
        return response.status == 200 and (
            payload.get("ok") is True or payload.get("status") == "ok"
        )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def execution_manifest(workspace: Path) -> ExecutionManifest:
    canonical = canonical_workspace(workspace)
    return {
        "filesystem_origin": "native_custodian",
        "selected_repository": str(canonical),
        "command_runtime": "native_custodian_host",
        "host_worker": "available" if host_worker_available() else "unavailable",
    }


def format_execution_manifest(manifest: ExecutionManifest) -> str:
    return "\n".join(
        (
            "Execution manifest (server-produced):",
            f"- filesystem origin: {manifest['filesystem_origin']}",
            f"- selected repository: {manifest['selected_repository']}",
            f"- command runtime: {manifest['command_runtime']}",
            f"- direct Custodian worker: {manifest['host_worker']}",
        )
    )
