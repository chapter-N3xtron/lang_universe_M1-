from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docker_broker.audit import AuditLog
from docker_broker.config import Settings
from docker_broker.errors import OperationError, PolicyError
from docker_broker.idempotency import IdempotencyStore
from docker_broker.leases import Lease
from docker_broker.models import (
    ComposeApplyRequest,
    RuntimeInspectResponse,
    ServiceSummary,
)
from docker_broker.policy import ValidatedProject


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    exit_code: int


@dataclass(frozen=True)
class ProjectSnapshot:
    root: Path
    project_directory: Path
    compose_file: Path
    override_file: Path
    empty_env_file: Path
    execution_file: Path
    content_digest: str
    managed_images: dict[str, str]


class DockerRunner:
    def __init__(self, settings: Settings, audit: AuditLog) -> None:
        self._settings = settings
        self._audit = audit
        self._idempotency = IdempotencyStore(
            settings.state_directory / "operations.sqlite3"
        )
        self._request_lock = asyncio.Lock()
        self._operation_slots = asyncio.Semaphore(2)
        self._active_process_groups: set[int] = set()
        docker_config = settings.state_directory / f"docker-config-{uuid.uuid4().hex}"
        docker_config.mkdir(mode=0o700)
        self._docker_config = docker_config
        if settings.cli_plugin_directory is not None:
            config_file = docker_config / "config.json"
            config_file.write_text(
                json.dumps(
                    {"cliPluginsExtraDirs": [str(settings.cli_plugin_directory)]},
                    separators=(",", ":"),
                )
            )
            os.chmod(config_file, 0o600)
        tool_paths = (
            settings.docker_path,
            settings.compose_plugin_path,
            settings.buildx_plugin_path,
        )
        self._tool_signatures = {
            path: self._file_signature(path) for path in tool_paths if path is not None
        }
        self._environment = {
            "PATH": f"{settings.docker_path.parent}:/usr/bin:/bin",
            "HOME": str(settings.state_directory),
            "DOCKER_CONFIG": str(docker_config),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
            "COMPOSE_DISABLE_ENV_FILE": "1",
            "COMPOSE_REMOVE_ORPHANS": "0",
            "COMPOSE_IGNORE_ORPHANS": "1",
            "COMPOSE_PROFILES": "",
            "COMPOSE_PARALLEL_LIMIT": "4",
            "COMPOSE_MENU": "0",
            "COMPOSE_EXPERIMENTAL": "0",
        }

    async def docker_available(self) -> bool:
        async with self._operation_slots:
            try:
                docker = await self._run(
                    [
                        str(self._settings.docker_path),
                        "version",
                        "--format",
                        "{{.Server.Version}}",
                    ],
                    timeout=10,
                    capture=True,
                )
                compose = await self._run(
                    [
                        str(self._settings.docker_path),
                        "compose",
                        "version",
                        "--short",
                    ],
                    timeout=10,
                    capture=True,
                )
                return bool(docker.stdout.strip() and compose.stdout.strip())
            except OperationError:
                return False

    async def validate_config(self, project: ValidatedProject) -> None:
        async with self._operation_slots:
            snapshot = await self._create_snapshot(project)
            try:
                await self._validate_snapshot(project, snapshot)
            finally:
                await asyncio.to_thread(self._remove_snapshot, snapshot)

    async def service_status(
        self, project: ValidatedProject
    ) -> tuple[ServiceSummary, ...]:
        async with self._operation_slots:
            snapshot = await self._create_snapshot(project)
            try:
                await self._validate_snapshot(project, snapshot)
                command = self._compose_prefix(project, snapshot, effective=True)
                command.extend(["ps", "--format", "json"])
                result = await self._run(command, timeout=30, capture=True)
            finally:
                await asyncio.to_thread(self._remove_snapshot, snapshot)
        states: dict[str, dict[str, Any]] = {}
        text = result.stdout.strip()
        if text:
            try:
                parsed = json.loads(text)
                rows = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                try:
                    rows = [
                        json.loads(line) for line in text.splitlines() if line.strip()
                    ]
                except json.JSONDecodeError as exc:
                    raise OperationError("Docker service status was malformed") from exc
            for row in rows:
                if isinstance(row, dict) and row.get("Service"):
                    states[str(row["Service"])] = row
        return tuple(
            ServiceSummary(
                name=summary.name,
                image=summary.image,
                build=summary.build,
                published_ports=summary.published_ports,
                state=str(states.get(summary.name, {}).get("State") or "not_running"),
            )
            for summary in project.summaries
        )

    async def apply(
        self,
        project: ValidatedProject,
        request: ComposeApplyRequest,
        lease: Lease,
    ) -> dict[str, Any]:
        async with self._request_lock, self._operation_slots:
            self._validate_request_services(project, request)
            snapshot = await self._create_snapshot(project)
            ledger_started = False
            ledger_succeeded = False
            try:
                await self._validate_snapshot(
                    project,
                    snapshot,
                    revoke_event=lease.revoked,
                    expires_monotonic=lease.expires_monotonic,
                )
                fingerprint = self._request_fingerprint(project, snapshot, request)
                previous = await asyncio.to_thread(
                    self._idempotency.begin,
                    lease.scope_digest,
                    request.request_id,
                    fingerprint,
                )
                if previous is not None:
                    return previous
                ledger_started = True
                remaining = lease.expires_monotonic - time.monotonic()
                if remaining <= 0 or lease.revoked.is_set():
                    raise OperationError("Docker session authority expired")
                if request.operation in {"build", "up"}:
                    await self._build_services(
                        project,
                        snapshot,
                        request,
                        lease,
                    )
                if request.operation != "build":
                    command = self._compose_prefix(project, snapshot, effective=True)
                    for profile in request.profiles:
                        if not profile or not all(
                            character.isalnum() or character in "_.-"
                            for character in profile
                        ):
                            raise PolicyError("invalid Compose profile")
                        command.extend(["--profile", profile])
                    command.extend(self._operation_arguments(request))
                    remaining = lease.expires_monotonic - time.monotonic()
                    if remaining <= 0 or lease.revoked.is_set():
                        raise OperationError("Docker session authority expired")
                    await self._run(
                        command,
                        timeout=min(
                            float(self._settings.operation_timeout_seconds), remaining
                        ),
                        revoke_event=lease.revoked,
                        capture=False,
                    )
                if (
                    lease.revoked.is_set()
                    or time.monotonic() >= lease.expires_monotonic
                ):
                    raise OperationError("Docker session authority was revoked")
                affected_services = self._affected_services(project, request)
                response = {
                    "request_id": request.request_id,
                    "status": "succeeded",
                    "operation": request.operation,
                    "project": project.project_name,
                    "services": affected_services,
                }
                await asyncio.to_thread(
                    self._audit.write,
                    "compose_operation_succeeded",
                    request_id=request.request_id,
                    session_id=lease.session_id,
                    owner_id=lease.owner_id,
                    workspace=str(lease.workspace),
                    project=project.project_name,
                    operation=request.operation,
                    services=affected_services,
                    snapshot_digest=snapshot.content_digest,
                )
                await asyncio.to_thread(
                    self._idempotency.succeed,
                    lease.scope_digest,
                    request.request_id,
                    response,
                )
                ledger_succeeded = True
                return response
            except BaseException:
                if ledger_started and not ledger_succeeded:
                    await asyncio.shield(
                        asyncio.to_thread(
                            self._idempotency.mark_unknown,
                            lease.scope_digest,
                            request.request_id,
                        )
                    )
                raise
            finally:
                await asyncio.to_thread(self._remove_snapshot, snapshot)

    async def inspect_langgraph(self) -> RuntimeInspectResponse:
        async with self._operation_slots:
            result = await self._run(
                [
                    str(self._settings.docker_path),
                    "inspect",
                    self._settings.langgraph_container,
                ],
                timeout=30,
                capture=True,
            )
        try:
            payload = json.loads(result.stdout)
            container = payload[0]
            state = container.get("State", {})
            host_config = container.get("HostConfig", {})
            health = state.get("Health", {}).get("Status")
            ports: list[str] = []
            for target, bindings in (
                container.get("NetworkSettings", {}).get("Ports") or {}
            ).items():
                for binding in bindings or []:
                    ports.append(
                        self._bounded(
                            f"{binding.get('HostIp')}:{binding.get('HostPort')}->{target}"
                        )
                    )
            networks = sorted(
                self._bounded(value)
                for value in (
                    container.get("NetworkSettings", {}).get("Networks") or {}
                )
            )
            mounts = [
                {
                    "type": self._bounded(mount.get("Type") or ""),
                    "destination": self._bounded(mount.get("Destination") or ""),
                    "read_write": bool(mount.get("RW")),
                }
                for mount in container.get("Mounts", [])[:128]
            ]
            socket_present = any(
                str(mount.get("Destination") or "").endswith(".sock")
                for mount in container.get("Mounts", [])
            )
            host_namespaces = (
                any(
                    str(host_config.get(key) or "") == "host"
                    for key in (
                        "PidMode",
                        "IpcMode",
                        "UTSMode",
                        "UsernsMode",
                        "CgroupnsMode",
                    )
                )
                or str(host_config.get("NetworkMode") or "") == "host"
            )
            return RuntimeInspectResponse(
                name=self._bounded(str(container.get("Name") or "").lstrip("/")),
                image=self._bounded(
                    str(container.get("Config", {}).get("Image") or "")
                ),
                status=self._bounded(str(state.get("Status") or "unknown")),
                health=self._bounded(str(health)) if health else None,
                platform=self._bounded(str(container.get("Platform")))
                if container.get("Platform")
                else None,
                ports=ports,
                networks=networks,
                mounts=mounts,
                docker_socket_present=socket_present,
                privileged=bool(host_config.get("Privileged")),
                host_namespaces_present=host_namespaces,
                devices_present=bool(host_config.get("Devices")),
            )
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OperationError(
                "LangGraph container metadata was unavailable"
            ) from exc

    async def close(self) -> None:
        groups = tuple(self._active_process_groups)
        await asyncio.gather(
            *(self._terminate_process_group(group, None) for group in groups),
            return_exceptions=True,
        )
        try:
            await asyncio.to_thread(shutil.rmtree, self._docker_config)
        except FileNotFoundError:
            pass

    async def _validate_snapshot(
        self,
        project: ValidatedProject,
        snapshot: ProjectSnapshot,
        *,
        revoke_event: asyncio.Event | None = None,
        expires_monotonic: float | None = None,
    ) -> None:
        timeout = 30.0
        if expires_monotonic is not None:
            timeout = min(timeout, max(0.0, expires_monotonic - time.monotonic()))
        if timeout <= 0 or (revoke_event and revoke_event.is_set()):
            raise OperationError("Docker session authority expired")
        command = self._compose_prefix(project, snapshot, effective=False)
        command.extend(["--profile", "*", "config", "--format", "json"])
        result = await self._run(
            command,
            timeout=timeout,
            revoke_event=revoke_event,
            capture=True,
        )
        try:
            effective = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OperationError(
                "Docker Compose canonical output was malformed"
            ) from exc
        self._validate_effective(project, snapshot, effective)
        escaped = self._escape_dollars(effective)
        os.chmod(snapshot.execution_file, 0o600)
        snapshot.execution_file.write_text(
            json.dumps(escaped, separators=(",", ":"), sort_keys=True)
        )
        os.chmod(snapshot.execution_file, 0o400)

    def _compose_prefix(
        self,
        project: ValidatedProject,
        snapshot: ProjectSnapshot,
        *,
        effective: bool,
    ) -> list[str]:
        command = [
            str(self._settings.docker_path),
            "compose",
            "--env-file",
            str(snapshot.empty_env_file),
            "--project-directory",
            str(snapshot.project_directory),
            "--project-name",
            project.project_name,
            "--file",
            str(snapshot.execution_file if effective else snapshot.compose_file),
        ]
        if not effective:
            command.extend(["--file", str(snapshot.override_file)])
        return command

    async def _build_services(
        self,
        project: ValidatedProject,
        snapshot: ProjectSnapshot,
        request: ComposeApplyRequest,
        lease: Lease,
    ) -> None:
        targets = [
            service
            for service in (request.services or list(project.build_services))
            if service in project.build_services
        ]
        if not targets:
            if request.operation == "build":
                raise PolicyError("build requires at least one buildable service")
            return
        builder = f"jasper-broker-{uuid.uuid4().hex[:20]}"
        remaining = lease.expires_monotonic - time.monotonic()
        await self._run(
            [
                str(self._settings.docker_path),
                "buildx",
                "create",
                "--name",
                builder,
                "--driver",
                "docker-container",
            ],
            timeout=min(60.0, remaining),
            revoke_event=lease.revoked,
            capture=False,
        )
        build_failed = False
        try:
            remaining = lease.expires_monotonic - time.monotonic()
            await self._run(
                [
                    str(self._settings.docker_path),
                    "buildx",
                    "bake",
                    "--builder",
                    builder,
                    "--file",
                    str(snapshot.execution_file),
                    "--load",
                    *targets,
                ],
                timeout=min(float(self._settings.operation_timeout_seconds), remaining),
                revoke_event=lease.revoked,
                capture=False,
            )
        except BaseException:
            build_failed = True
            raise
        finally:
            try:
                await asyncio.shield(
                    self._run(
                        [
                            str(self._settings.docker_path),
                            "buildx",
                            "rm",
                            "--force",
                            builder,
                        ],
                        timeout=60,
                        capture=False,
                    )
                )
            except (OperationError, asyncio.CancelledError):
                await asyncio.to_thread(
                    self._audit.write,
                    "build_isolation_cleanup_failed",
                    builder=builder,
                    build_failed=build_failed,
                )
                if not build_failed:
                    raise OperationError("Build isolation cleanup failed")

    @staticmethod
    def _operation_arguments(request: ComposeApplyRequest) -> list[str]:
        services = list(request.services)
        if request.operation == "pull":
            return ["pull", *services]
        if request.operation == "up":
            return ["up", "--detach", "--no-build", *services]
        if request.operation in {"start", "stop", "restart"}:
            return [request.operation, *services]
        return ["down"]

    @staticmethod
    def _validate_request_services(
        project: ValidatedProject, request: ComposeApplyRequest
    ) -> None:
        if any(service not in project.service_names for service in request.services):
            raise PolicyError("operation references an unknown service")
        if request.operation == "down" and request.services:
            raise PolicyError("down cannot target individual services")
        if request.operation == "pull":
            targets = set(request.services or project.service_names)
            if targets.intersection(project.build_services):
                raise PolicyError("buildable services must use build rather than pull")
        if (
            request.operation == "build"
            and request.services
            and any(
                service not in project.build_services for service in request.services
            )
        ):
            raise PolicyError("build can target only buildable services")

    @staticmethod
    def _affected_services(
        project: ValidatedProject, request: ComposeApplyRequest
    ) -> list[str]:
        if request.services:
            return list(request.services)
        if request.operation == "build":
            return list(project.build_services)
        return list(project.service_names)

    async def _create_snapshot(self, project: ValidatedProject) -> ProjectSnapshot:
        task = asyncio.create_task(asyncio.to_thread(self._snapshot, project))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            result = (
                await asyncio.shield(asyncio.gather(task, return_exceptions=True))
            )[0]
            if isinstance(result, ProjectSnapshot):
                await asyncio.to_thread(self._remove_snapshot, result)
            raise

    def _snapshot(self, project: ValidatedProject) -> ProjectSnapshot:
        root = Path(
            tempfile.mkdtemp(prefix="operation-", dir=self._settings.state_directory)
        )
        os.chmod(root, 0o700)
        destination = root / "project"
        destination.mkdir(mode=0o700)
        try:
            self._copy_project(project.project_directory, destination)
            content_digest = self._directory_digest(destination)
            effective_document = copy.deepcopy(project.compose_document)
            managed_images: dict[str, str] = {}
            for service_name in project.build_services:
                image_service = re.sub(
                    r"[^a-z0-9_.-]+", "-", service_name.lower()
                ).strip("-._")
                image = (
                    "jasper-broker-managed/"
                    f"{project.workspace_digest[:16]}/"
                    f"{project.project_name}-{image_service or 'service'}:"
                    f"{content_digest[:24]}"
                )
                managed_images[service_name] = image
                service = effective_document["services"][service_name]
                service["image"] = image
                service["pull_policy"] = "never"
            relative_compose = project.compose_file.relative_to(
                project.project_directory
            )
            compose_file = destination / relative_compose
            compose_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            compose_file.write_text(
                json.dumps(effective_document, separators=(",", ":"), sort_keys=True)
            )
            override_file = root / "policy-override.json"
            override_file.write_text(
                json.dumps(project.override, separators=(",", ":"), sort_keys=True)
            )
            empty_env_file = root / "empty.env"
            empty_env_file.write_text("")
            execution_file = root / "effective-compose.yaml"
            execution_file.write_text("{}")
            for path in (compose_file, override_file, empty_env_file):
                os.chmod(path, 0o400)
            os.chmod(execution_file, 0o600)
            self._make_tree_read_only(destination)
            return ProjectSnapshot(
                root=root,
                project_directory=destination,
                compose_file=compose_file,
                override_file=override_file,
                empty_env_file=empty_env_file,
                execution_file=execution_file,
                content_digest=content_digest,
                managed_images=managed_images,
            )
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def _copy_project(self, source: Path, destination: Path) -> None:
        counters = {"entries": 0, "bytes": 0}
        flags = (
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        source_fd = os.open(source, flags)
        destination_fd = os.open(destination, flags)
        try:
            self._copy_directory_fd(
                source_fd,
                destination_fd,
                counters,
                root=True,
                depth=0,
            )
        finally:
            os.close(destination_fd)
            os.close(source_fd)

    def _copy_directory_fd(
        self,
        source_fd: int,
        destination_fd: int,
        counters: dict[str, int],
        *,
        root: bool = False,
        depth: int,
    ) -> None:
        if depth > 64:
            raise PolicyError("project snapshot exceeds directory depth limit")
        entries = sorted(os.scandir(source_fd), key=lambda entry: entry.name)
        for entry in entries:
            name = entry.name
            if root and name == ".git":
                continue
            counters["entries"] += 1
            if counters["entries"] > self._settings.max_snapshot_files:
                raise PolicyError("project snapshot exceeds broker limits")
            if name in {".", ".."} or "\x00" in name:
                raise PolicyError("invalid project entry")
            if entry.is_symlink():
                raise PolicyError("project snapshots do not permit symlinks")
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                os.mkdir(name, 0o700, dir_fd=destination_fd)
                flags = (
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                child_source = os.open(name, flags, dir_fd=source_fd)
                child_destination = os.open(name, flags, dir_fd=destination_fd)
                try:
                    self._copy_directory_fd(
                        child_source,
                        child_destination,
                        counters,
                        depth=depth + 1,
                    )
                finally:
                    os.close(child_destination)
                    os.close(child_source)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise PolicyError(
                        "project snapshots do not permit hard-linked files"
                    )
                source_file = os.open(
                    name,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=source_fd,
                )
                opened_metadata = os.fstat(source_file)
                if (
                    not stat.S_ISREG(opened_metadata.st_mode)
                    or opened_metadata.st_nlink != 1
                ):
                    os.close(source_file)
                    raise PolicyError("project file changed during snapshot")
                mode = 0o700 if opened_metadata.st_mode & stat.S_IXUSR else 0o600
                destination_file = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    mode,
                    dir_fd=destination_fd,
                )
                try:
                    while chunk := os.read(source_file, 1024 * 1024):
                        counters["bytes"] += len(chunk)
                        if counters["bytes"] > self._settings.max_snapshot_bytes:
                            raise PolicyError("project snapshot exceeds broker limits")
                        view = memoryview(chunk)
                        while view:
                            view = view[os.write(destination_file, view) :]
                finally:
                    os.close(destination_file)
                    os.close(source_file)
            else:
                raise PolicyError("project snapshot contains an unsupported file type")

    @staticmethod
    def _make_tree_read_only(directory: Path) -> None:
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_dir():
                os.chmod(path, 0o500)
            elif path.is_file():
                executable = path.stat().st_mode & stat.S_IXUSR
                os.chmod(path, 0o500 if executable else 0o400)
        os.chmod(directory, 0o500)

    @staticmethod
    def _directory_digest(directory: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory).as_posix().encode()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            if path.is_file():
                digest.update(b"F")
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
            elif path.is_dir():
                digest.update(b"D")
        return digest.hexdigest()

    @staticmethod
    def _remove_snapshot(snapshot: ProjectSnapshot) -> None:
        for path in sorted(snapshot.root.rglob("*"), reverse=True):
            try:
                os.chmod(path, 0o700 if path.is_dir() else 0o600)
            except OSError:
                pass
        shutil.rmtree(snapshot.root, ignore_errors=True)

    def _request_fingerprint(
        self,
        project: ValidatedProject,
        snapshot: ProjectSnapshot,
        request: ComposeApplyRequest,
    ) -> str:
        value = {
            "project": project.project_name,
            "snapshot_digest": snapshot.content_digest,
            "managed_images": snapshot.managed_images,
            "policy_version": self._settings.policy_version,
            "operation": request.operation,
            "services": request.services,
            "profiles": request.profiles,
        }
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _validate_effective(
        self,
        project: ValidatedProject,
        snapshot: ProjectSnapshot,
        value: Any,
    ) -> None:
        if not isinstance(value, dict) or not isinstance(value.get("services"), dict):
            raise PolicyError("effective Compose model is invalid")
        services = value["services"]
        if set(services) != set(project.service_names):
            raise PolicyError("effective Compose services changed unexpectedly")
        expected_memory = self._memory_bytes(self._settings.default_memory_limit)
        for name in project.service_names:
            service = services.get(name)
            if not isinstance(service, dict):
                raise PolicyError("effective service model is invalid")
            expected_image = snapshot.managed_images.get(
                name,
                str(project.compose_document["services"][name].get("image") or ""),
            )
            if service.get("image") != expected_image:
                raise PolicyError("effective image reference changed unexpectedly")
            forbidden_truthy = (
                "privileged",
                "devices",
                "cap_add",
                "security_opt",
                "device_cgroup_rules",
            )
            if any(service.get(key) for key in forbidden_truthy):
                raise PolicyError("effective service gained forbidden authority")
            if any(
                str(service.get(key) or "") == "host"
                for key in ("network_mode", "pid", "ipc", "cgroup")
            ):
                raise PolicyError("effective service gained a host namespace")
            self._validate_effective_ports(service.get("ports"))
            self._validate_effective_mounts(service.get("volumes"))
            labels = service.get("labels") or {}
            if not isinstance(labels, dict):
                raise PolicyError("effective labels are invalid")
            expected_labels = project.override["services"][name]["labels"]
            if any(
                labels.get(key) != expected for key, expected in expected_labels.items()
            ):
                raise PolicyError("broker ownership labels were not enforced")
            if int(service.get("pids_limit") or 0) != self._settings.default_pids_limit:
                raise PolicyError("effective PID limit was not enforced")
            if float(service.get("cpus") or 0) != float(self._settings.default_cpus):
                raise PolicyError("effective CPU limit was not enforced")
            if int(service.get("mem_limit") or 0) != expected_memory:
                raise PolicyError("effective memory limit was not enforced")
        for definition in (value.get("volumes") or {}).values():
            if not isinstance(definition, dict):
                raise PolicyError("effective volume model is invalid")
            if definition.get("external") or definition.get("driver_opts"):
                raise PolicyError("effective volume references external host state")
            if definition.get("driver") not in (None, "", "local"):
                raise PolicyError("effective volume driver is not allowed")
        for definition in (value.get("networks") or {}).values():
            if not isinstance(definition, dict):
                raise PolicyError("effective network model is invalid")
            if definition.get("external") or definition.get("driver_opts"):
                raise PolicyError("effective network references external host state")
            if definition.get("driver") not in (None, "", "bridge"):
                raise PolicyError("effective network driver is not allowed")

    def _validate_effective_ports(self, value: Any) -> None:
        for item in value or []:
            if not isinstance(item, dict):
                raise PolicyError("effective published port is invalid")
            try:
                published = int(item.get("published"))
            except (TypeError, ValueError) as exc:
                raise PolicyError("effective published port is invalid") from exc
            if (
                item.get("host_ip") != "127.0.0.1"
                or not 1 <= published <= 65535
                or published in self._settings.reserved_ports
            ):
                raise PolicyError("effective published port violates loopback policy")

    @staticmethod
    def _validate_effective_mounts(value: Any) -> None:
        for item in value or []:
            if not isinstance(item, dict) or item.get("type") not in {
                "volume",
                "tmpfs",
            }:
                raise PolicyError("effective mount violates storage policy")
            target = str(item.get("target") or "")
            if not target.startswith("/") or target.endswith(".sock"):
                raise PolicyError("effective mount destination is invalid")

    @staticmethod
    def _escape_dollars(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("$", "$$")
        if isinstance(value, list):
            return [DockerRunner._escape_dollars(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): DockerRunner._escape_dollars(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _memory_bytes(value: str) -> int:
        match = re.fullmatch(r"([0-9]+)([kKmMgG])?", value)
        if not match:
            raise ValueError("invalid configured memory limit")
        amount = int(match.group(1))
        multiplier = {
            None: 1,
            "k": 1024,
            "m": 1024**2,
            "g": 1024**3,
        }[match.group(2).lower() if match.group(2) else None]
        return amount * multiplier

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int, int, int, int, int]:
        metadata = path.stat()
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_mode,
            metadata.st_uid,
        )

    def _verify_toolchain(self) -> None:
        try:
            changed = any(
                self._file_signature(path) != signature
                for path, signature in self._tool_signatures.items()
            )
        except OSError as exc:
            raise OperationError("Docker toolchain is unavailable") from exc
        if changed:
            raise OperationError("Docker toolchain changed after broker startup")

    async def _run(
        self,
        command: list[str],
        *,
        timeout: float,
        capture: bool,
        revoke_event: asyncio.Event | None = None,
    ) -> CommandResult:
        if timeout <= 0 or (revoke_event and revoke_event.is_set()):
            raise OperationError("Docker session authority is absent")
        self._verify_toolchain()
        stdout_target = (
            asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self._settings.state_directory),
                env=self._environment,
                stdout=stdout_target,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise OperationError("Docker operation could not start") from exc
        process_group = process.pid
        self._active_process_groups.add(process_group)
        wait_task = asyncio.create_task(process.wait())
        output_task = (
            asyncio.create_task(self._read_bounded(process.stdout))
            if capture and process.stdout
            else None
        )
        revoke_task = asyncio.create_task(revoke_event.wait()) if revoke_event else None
        timeout_task = asyncio.create_task(asyncio.sleep(timeout))
        output = ""
        normal_completion = False
        try:
            while True:
                pending = {timeout_task}
                if not wait_task.done():
                    pending.add(wait_task)
                if output_task and not output_task.done():
                    pending.add(output_task)
                if revoke_task and not revoke_task.done():
                    pending.add(revoke_task)
                if (
                    not pending
                    or pending == {timeout_task}
                    and wait_task.done()
                    and (output_task is None or output_task.done())
                ):
                    break
                done, _ = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if output_task and output_task in done:
                    output = output_task.result()
                if revoke_task and revoke_task in done:
                    raise OperationError("Docker session authority was revoked")
                if timeout_task in done:
                    raise OperationError("Docker operation timed out")
                if wait_task.done() and (output_task is None or output_task.done()):
                    break
            if revoke_event and revoke_event.is_set():
                raise OperationError("Docker session authority was revoked")
            if not wait_task.done():
                await wait_task
            if output_task:
                if not output_task.done():
                    output = await output_task
                else:
                    output = output_task.result()
            if process.returncode != 0:
                await asyncio.to_thread(
                    self._audit.write,
                    "docker_operation_failed",
                    executable=Path(command[0]).name,
                    operation=command[1] if len(command) > 1 else "unknown",
                    exit_code=process.returncode,
                )
                raise OperationError("Docker operation failed")
            normal_completion = True
            return CommandResult(stdout=output, exit_code=process.returncode or 0)
        finally:
            for task in (wait_task, output_task, revoke_task, timeout_task):
                if task and not task.done():
                    task.cancel()
            if not normal_completion:
                await asyncio.shield(
                    self._terminate_process_group(process_group, process)
                )
            self._active_process_groups.discard(process_group)

    async def _terminate_process_group(
        self,
        process_group: int,
        process: asyncio.subprocess.Process | None,
    ) -> None:
        try:
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            pass
        await asyncio.sleep(0.2)
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process is not None and process.returncode is None:
            await process.wait()

    async def _read_bounded(self, stream: asyncio.StreamReader) -> str:
        chunks: list[bytes] = []
        total = 0
        while chunk := await stream.read(16_384):
            total += len(chunk)
            if total > self._settings.max_output_bytes:
                raise OperationError("Docker output exceeded broker limits")
            chunks.append(chunk)
        return b"".join(chunks).decode(errors="replace")

    @staticmethod
    def _bounded(value: Any) -> str:
        text = str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ")
        return text[:512]
