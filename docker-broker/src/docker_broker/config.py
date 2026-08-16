from __future__ import annotations

import hashlib
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from docker_broker.langgraph import AgentServerPendingInterruptChecker


@dataclass(frozen=True)
class Settings:
    allowed_roots: tuple[Path, ...]
    state_directory: Path
    agent_server_url: str
    owner_id: str
    docker_path: Path = Path("/usr/local/bin/docker")
    git_path: Path = Path("/usr/bin/git")
    osascript_path: Path = Path("/usr/bin/osascript")
    langgraph_container: str = "backend-langgraph-api-1"
    operation_timeout_seconds: int = 900
    max_output_bytes: int = 100_000
    max_services: int = 40
    max_snapshot_bytes: int = 500_000_000
    max_snapshot_files: int = 20_000
    default_memory_limit: str = "2g"
    default_cpus: str = "2.0"
    default_pids_limit: int = 512
    reserved_ports: tuple[int, ...] = (3001, 5432, 6379, 8000, 8123, 8765, 8766)
    client_secret: str | None = None
    cli_plugin_directory: Path | None = None
    compose_plugin_path: Path | None = None
    buildx_plugin_path: Path | None = None
    allow_builds: bool = False
    lease_seconds: int = 14400

    @classmethod
    def from_values(
        cls,
        *,
        allowed_roots: list[str],
        state_directory: str,
        agent_server_url: str,
        owner_id: str,
        docker_path: str = "/usr/local/bin/docker",
        lease_seconds: int = 14400,
        allow_builds: bool = False,
    ) -> Settings:
        if not allowed_roots:
            raise ValueError("at least one allowed repository root is required")
        if (
            not owner_id
            or len(owner_id) > 128
            or any(
                not (character.isalnum() or character in "_.:-")
                for character in owner_id
            )
        ):
            raise ValueError("owner id is invalid")
        if not 300 <= lease_seconds <= 43200:
            raise ValueError("lease seconds must be between 300 and 43200")
        AgentServerPendingInterruptChecker(agent_server_url)
        roots = tuple(
            Path(value).expanduser().resolve(strict=True) for value in allowed_roots
        )
        raw_state = Path(state_directory).expanduser()
        raw_state.mkdir(mode=0o700, parents=True, exist_ok=True)
        state = raw_state.resolve(strict=True)
        if any(
            state.is_relative_to(root) or root.is_relative_to(state) for root in roots
        ):
            raise ValueError("broker state must not overlap an allowed repository")
        state_metadata = state.stat()
        if not stat.S_ISDIR(state_metadata.st_mode):
            raise ValueError("broker state must be a directory")
        if state_metadata.st_uid != os.geteuid():
            raise ValueError("broker state must be owned by the broker user")
        os.chmod(state, 0o700)
        docker = cls._trusted_executable(
            Path(docker_path).expanduser(), roots, "docker"
        )
        plugin_candidates = (
            docker.parent.parent / "cli-plugins",
            docker.parent / "cli-plugins",
            Path("/usr/local/lib/docker/cli-plugins"),
        )
        plugin_directory = next(
            (
                candidate.resolve(strict=True)
                for candidate in plugin_candidates
                if (candidate / "docker-compose").is_file()
            ),
            None,
        )
        if plugin_directory is None:
            raise ValueError("trusted Docker Compose plugin was not found")
        plugin_metadata = plugin_directory.stat()
        if (
            plugin_metadata.st_uid not in {0, os.geteuid()}
            or plugin_metadata.st_mode & 0o022
            or any(plugin_directory.is_relative_to(root) for root in roots)
        ):
            raise ValueError("Docker CLI plugin directory is not trusted")
        compose_plugin = cls._trusted_executable(
            plugin_directory / "docker-compose", roots, "docker-compose"
        )
        buildx_candidate = plugin_directory / "docker-buildx"
        buildx_plugin = (
            cls._trusted_executable(buildx_candidate, roots, "docker-buildx")
            if buildx_candidate.is_file()
            else None
        )
        if allow_builds and buildx_plugin is None:
            raise ValueError("trusted Docker Buildx plugin was not found")
        git = cls._trusted_executable(Path("/usr/bin/git"), roots, "git")
        osascript = cls._trusted_executable(
            Path("/usr/bin/osascript"), roots, "osascript"
        )
        client_secret = cls._load_or_create_client_secret(state / "client-secret")
        return cls(
            allowed_roots=roots,
            state_directory=state,
            docker_path=docker,
            git_path=git,
            osascript_path=osascript,
            client_secret=client_secret,
            cli_plugin_directory=plugin_directory,
            compose_plugin_path=compose_plugin,
            buildx_plugin_path=buildx_plugin,
            allow_builds=allow_builds,
            agent_server_url=agent_server_url,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    @staticmethod
    def _trusted_executable(
        path: Path, allowed_roots: tuple[Path, ...], name: str
    ) -> Path:
        resolved = path.resolve(strict=True)
        if any(resolved.is_relative_to(root) for root in allowed_roots):
            raise ValueError(f"{name} executable must be outside allowed repositories")
        metadata = resolved.stat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid not in {0, os.geteuid()}
            or metadata.st_mode & 0o022
            or not os.access(resolved, os.X_OK)
        ):
            raise ValueError(f"{name} executable is not trusted")
        return resolved

    @staticmethod
    def _load_or_create_client_secret(path: Path) -> str:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(path, flags, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077
            ):
                raise ValueError("broker client secret file is unsafe")
            value = os.read(descriptor, 256).decode().strip()
            if not value:
                value = secrets.token_urlsafe(48)
                os.write(descriptor, (value + "\n").encode())
                os.fsync(descriptor)
            if not 32 <= len(value) <= 128:
                raise ValueError("broker client secret is invalid")
            return value
        finally:
            os.close(descriptor)

    @property
    def policy_version(self) -> str:
        fields = (
            *(str(path) for path in self.allowed_roots),
            *(str(port) for port in self.reserved_ports),
            str(self.max_services),
            str(self.max_snapshot_bytes),
            str(self.max_snapshot_files),
            self.default_memory_limit,
            self.default_cpus,
            str(self.default_pids_limit),
            str(self.allow_builds),
        )
        return "sha256:" + hashlib.sha256("\0".join(fields).encode()).hexdigest()
