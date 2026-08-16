from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError
from yaml.tokens import AliasToken, AnchorToken

from docker_broker.config import Settings
from docker_broker.errors import PolicyError
from docker_broker.models import ComposeTarget, ServiceSummary

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DIGEST_IMAGE = re.compile(r"^[^\s@$]+(?:/[^\s@$]+)*@sha256:[0-9a-fA-F]{64}$")
_RESERVED_LABEL_PREFIX = "jasper.docker-broker."
_ALLOWED_TOP_LEVEL = {"version", "services", "volumes", "networks"}
_ALLOWED_SERVICE_KEYS = {
    "build",
    "command",
    "depends_on",
    "entrypoint",
    "environment",
    "expose",
    "healthcheck",
    "image",
    "init",
    "labels",
    "mem_limit",
    "networks",
    "pids_limit",
    "ports",
    "profiles",
    "pull_policy",
    "read_only",
    "restart",
    "shm_size",
    "stop_grace_period",
    "stop_signal",
    "tty",
    "user",
    "volumes",
    "working_dir",
}
_ALLOWED_BUILD_KEYS = {
    "args",
    "context",
    "dockerfile",
    "dockerfile_inline",
    "labels",
    "no_cache",
    "pull",
    "target",
}


@dataclass(frozen=True)
class ValidatedProject:
    workspace: Path
    project_directory: Path
    compose_file: Path
    compose_document: dict[str, Any]
    project_name: str
    workspace_digest: str
    service_names: tuple[str, ...]
    build_services: tuple[str, ...]
    summaries: tuple[ServiceSummary, ...]
    override: dict[str, Any]


class ComposePolicy:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve_workspace(self, value: str) -> Path:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            raise PolicyError("workspace must be absolute")
        try:
            workspace = candidate.resolve(strict=True)
        except OSError as exc:
            raise PolicyError("workspace is unavailable") from exc
        if not workspace.is_dir():
            raise PolicyError("workspace must be a directory")
        if not any(
            workspace.is_relative_to(root) for root in self._settings.allowed_roots
        ):
            raise PolicyError("workspace is outside configured repository roots")
        environment = {"PATH": f"{self._settings.git_path.parent}:/usr/bin:/bin"}
        try:
            result = subprocess.run(
                [
                    str(self._settings.git_path),
                    "-C",
                    str(workspace),
                    "rev-parse",
                    "--show-toplevel",
                ],
                capture_output=True,
                check=True,
                env=environment,
                text=True,
                timeout=10,
            )
            repository = Path(result.stdout.strip()).resolve(strict=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PolicyError("workspace is not a readable Git repository") from exc
        if repository != workspace:
            raise PolicyError("workspace must be the repository root")
        return workspace

    def validate(self, workspace: Path, target: ComposeTarget) -> ValidatedProject:
        if len(target.compose_files) != 1:
            raise PolicyError("exactly one Compose file is supported")
        project_directory = self._resolve_relative(
            workspace,
            target.project_directory,
            require_directory=True,
        )
        compose_file = self._resolve_relative(
            project_directory,
            target.compose_files[0],
            require_file=True,
        )
        document = self._load_document(compose_file)
        self._validate_top_level(document)
        services = document["services"]
        if not 1 <= len(services) <= self._settings.max_services:
            raise PolicyError("compose project service count is outside policy")
        declared_services = {str(name) for name in services}
        declared_volumes = self._validate_volumes_definition(document.get("volumes"))
        declared_networks = self._validate_networks_definition(document.get("networks"))
        summaries: list[ServiceSummary] = []
        build_services: list[str] = []
        for raw_name, raw_service in sorted(
            services.items(), key=lambda item: str(item[0])
        ):
            name = str(raw_name)
            if not isinstance(raw_service, Mapping):
                raise PolicyError("service definitions must be mappings")
            service = dict(raw_service)
            self._validate_service(
                name,
                service,
                project_directory,
                declared_services,
                declared_volumes,
                declared_networks,
            )
            summaries.append(self._service_summary(name, service))
            if "build" in service:
                build_services.append(name)
        digest = hashlib.sha256(
            f"{workspace}\0{project_directory}".encode()
        ).hexdigest()[:12]
        prefix = re.sub(r"[^a-z0-9-]+", "-", project_directory.name.lower()).strip("-")
        prefix = (prefix or "compose")[:32].rstrip("-") or "compose"
        project_name = f"jasper-{prefix}-{digest}"
        workspace_digest = hashlib.sha256(str(workspace).encode()).hexdigest()
        override = {
            "services": {
                name: {
                    "mem_limit": self._settings.default_memory_limit,
                    "cpus": self._settings.default_cpus,
                    "pids_limit": self._settings.default_pids_limit,
                    "labels": {
                        f"{_RESERVED_LABEL_PREFIX}managed": "true",
                        f"{_RESERVED_LABEL_PREFIX}project": project_name,
                        f"{_RESERVED_LABEL_PREFIX}workspace": workspace_digest,
                    },
                }
                for name in declared_services
            }
        }
        return ValidatedProject(
            workspace=workspace,
            project_directory=project_directory,
            compose_file=compose_file,
            compose_document=document,
            project_name=project_name,
            workspace_digest=workspace_digest,
            service_names=tuple(sorted(declared_services)),
            build_services=tuple(sorted(build_services)),
            summaries=tuple(summaries),
            override=override,
        )

    def _resolve_relative(
        self,
        base: Path,
        raw: str,
        *,
        require_file: bool = False,
        require_directory: bool = False,
    ) -> Path:
        if not raw or len(raw) > 1024 or "\x00" in raw or "\\" in raw:
            raise PolicyError("invalid relative path")
        pure = PurePosixPath(raw)
        if pure.is_absolute() or ".." in pure.parts:
            raise PolicyError("path must remain inside the repository")
        try:
            resolved = (base / Path(*pure.parts)).resolve(strict=True)
        except OSError as exc:
            raise PolicyError("referenced path is unavailable") from exc
        if not resolved.is_relative_to(base):
            raise PolicyError("path escapes its allowed directory")
        if require_file and (
            not resolved.is_file() or resolved.stat().st_size > 1_000_000
        ):
            raise PolicyError("compose file must be a regular file under 1 MB")
        if require_directory and not resolved.is_dir():
            raise PolicyError("project directory must be a directory")
        return resolved

    @staticmethod
    def _load_document(path: Path) -> dict[str, Any]:
        try:
            text = path.read_text()
            if any(
                isinstance(token, (AliasToken, AnchorToken))
                for token in yaml.scan(text)
            ):
                raise PolicyError("YAML aliases and anchors are not supported")
            parser = YAML(typ="safe", pure=True)
            parser.version = (1, 2)
            value = parser.load(text)
        except PolicyError:
            raise
        except (OSError, UnicodeError, yaml.YAMLError, RuamelYAMLError) as exc:
            raise PolicyError("compose file is not valid YAML") from exc
        if not isinstance(value, Mapping):
            raise PolicyError("compose file must contain a mapping")
        return dict(value)

    @staticmethod
    def _validate_top_level(document: Mapping[str, Any]) -> None:
        unknown = {
            str(key)
            for key in document
            if key not in _ALLOWED_TOP_LEVEL and not str(key).startswith("x-")
        }
        if unknown:
            raise PolicyError("compose file contains unsupported top-level options")
        services = document.get("services")
        if not isinstance(services, Mapping):
            raise PolicyError("compose services must be a mapping")

    @staticmethod
    def _validate_volumes_definition(value: Any) -> set[str]:
        if value is None:
            return set()
        if not isinstance(value, Mapping):
            raise PolicyError("compose volumes must be a mapping")
        names: set[str] = set()
        for raw_name, definition in value.items():
            name = str(raw_name)
            if not _SAFE_NAME.fullmatch(name):
                raise PolicyError("invalid volume name")
            if definition not in (None, {}):
                raise PolicyError("volume drivers, names, and options are not allowed")
            names.add(name)
        return names

    @staticmethod
    def _validate_networks_definition(value: Any) -> set[str]:
        if value is None:
            return set()
        if not isinstance(value, Mapping):
            raise PolicyError("compose networks must be a mapping")
        names: set[str] = set()
        for raw_name, definition in value.items():
            name = str(raw_name)
            if not _SAFE_NAME.fullmatch(name):
                raise PolicyError("invalid network name")
            if definition is None:
                config: Mapping[str, Any] = {}
            elif isinstance(definition, Mapping):
                config = definition
            else:
                raise PolicyError("invalid network definition")
            if set(config) - {"internal"} or not isinstance(
                config.get("internal", False), bool
            ):
                raise PolicyError("custom and external network options are not allowed")
            names.add(name)
        return names

    def _validate_service(
        self,
        name: str,
        service: dict[str, Any],
        project_directory: Path,
        declared_services: set[str],
        declared_volumes: set[str],
        declared_networks: set[str],
    ) -> None:
        if not _SAFE_NAME.fullmatch(name):
            raise PolicyError("invalid service name")
        unknown = set(service) - _ALLOWED_SERVICE_KEYS
        if unknown:
            raise PolicyError("service contains unsupported options")
        labels = service.get("labels", {}) or {}
        self._validate_labels(labels)
        image = service.get("image")
        has_build = "build" in service
        if has_build:
            self._validate_build(service["build"], project_directory)
            if image is not None and (len(str(image)) > 512 or "\x00" in str(image)):
                raise PolicyError("invalid build image reference")
        elif not image or not _DIGEST_IMAGE.fullmatch(str(image)):
            raise PolicyError("image-only services must use a sha256 digest reference")
        self._validate_environment(service.get("environment"))
        if isinstance(service.get("build"), Mapping):
            self._validate_environment(service["build"].get("args"))
        self._validate_ports(service.get("ports"))
        self._validate_mounts(service.get("volumes"), declared_volumes)
        self._validate_network_references(service.get("networks"), declared_networks)
        self._validate_dependencies(service.get("depends_on"), declared_services)
        self._validate_profiles(service.get("profiles"))
        self._validate_restart(service.get("restart"))
        self._validate_healthcheck(service.get("healthcheck"))
        self._validate_size(service.get("shm_size"), maximum=1024**3)
        self._validate_duration(service.get("stop_grace_period"), maximum_seconds=60)
        pull_policy = service.get("pull_policy")
        if pull_policy not in (None, "always", "never", "missing", "build"):
            raise PolicyError("unsupported image pull policy")
        for key in ("mem_limit", "pids_limit"):
            if key in service and service[key] in (None, "", 0, "0"):
                raise PolicyError("resource limits must be positive")

    def _validate_build(self, value: Any, project_directory: Path) -> None:
        if not self._settings.allow_builds:
            raise PolicyError("builds are disabled on this broker")
        if isinstance(value, str):
            self._resolve_project_source(
                project_directory, value, require_directory=True
            )
            return
        if not isinstance(value, Mapping):
            raise PolicyError("build configuration must be a path or mapping")
        unknown = set(value) - _ALLOWED_BUILD_KEYS
        if unknown:
            raise PolicyError("build contains unsupported options")
        context = self._resolve_project_source(
            project_directory,
            str(value.get("context", ".")),
            require_directory=True,
        )
        dockerfile = value.get("dockerfile")
        if dockerfile:
            dockerfile_relative = Path(str(dockerfile))
            if dockerfile_relative.is_absolute() or ".." in dockerfile_relative.parts:
                raise PolicyError("Dockerfile must use a relative project path")
            try:
                dockerfile_path = (context / dockerfile_relative).resolve(strict=True)
            except OSError as exc:
                raise PolicyError("Dockerfile is unavailable") from exc
            if not dockerfile_path.is_file() or not dockerfile_path.is_relative_to(
                project_directory
            ):
                raise PolicyError("Dockerfile must remain inside the project directory")
        inline = value.get("dockerfile_inline")
        if inline and len(str(inline).encode()) > 200_000:
            raise PolicyError("inline Dockerfile is too large")
        self._validate_labels(value.get("labels", {}) or {})

    @staticmethod
    def _validate_labels(value: Any) -> None:
        if isinstance(value, Mapping):
            names = [str(key) for key in value]
        elif isinstance(value, list):
            names = [str(item).split("=", 1)[0] for item in value]
        else:
            raise PolicyError("labels must be a mapping or list")
        if any(name.startswith(_RESERVED_LABEL_PREFIX) for name in names):
            raise PolicyError("broker ownership labels are reserved")
        if any(len(name) > 256 or "\x00" in name or "$" in name for name in names):
            raise PolicyError("invalid label name")

    @staticmethod
    def _validate_environment(value: Any) -> None:
        if value is None:
            return
        pairs: list[tuple[str, Any]] = []
        if isinstance(value, Mapping):
            pairs = [(str(key), item) for key, item in value.items()]
        elif isinstance(value, list):
            if len(value) > 256:
                raise PolicyError("too many environment variables")
            for item in value:
                key, separator, raw = str(item).partition("=")
                pairs.append((key, raw if separator else None))
        else:
            raise PolicyError("environment must be a mapping or list")
        for key, _item in pairs:
            if not _SAFE_NAME.fullmatch(key):
                raise PolicyError("invalid environment variable name")

    def _validate_ports(self, value: Any) -> None:
        for item in self._as_list(value, maximum=64):
            host_ip: str | None = None
            published: int | None = None
            if isinstance(item, Mapping):
                if set(item) - {
                    "target",
                    "published",
                    "host_ip",
                    "protocol",
                    "mode",
                    "name",
                    "app_protocol",
                }:
                    raise PolicyError("published port contains unsupported options")
                host_ip = str(item.get("host_ip") or "")
                raw_published = item.get("published")
                if isinstance(raw_published, int) or str(raw_published or "").isdigit():
                    published = int(raw_published)
            else:
                text = str(item).split("/", 1)[0]
                parts = text.split(":")
                if len(parts) == 3:
                    host_ip = parts[0]
                    if parts[1].isdigit():
                        published = int(parts[1])
            if host_ip != "127.0.0.1" or published is None:
                raise PolicyError("published ports must explicitly bind to 127.0.0.1")
            if (
                published in self._settings.reserved_ports
                or not 1 <= published <= 65535
            ):
                raise PolicyError("published port is reserved or invalid")

    @staticmethod
    def _validate_mounts(value: Any, declared_volumes: set[str]) -> None:
        for item in ComposePolicy._as_list(value, maximum=128):
            if isinstance(item, Mapping):
                if set(item) - {
                    "type",
                    "source",
                    "target",
                    "read_only",
                    "volume",
                    "tmpfs",
                    "consistency",
                }:
                    raise PolicyError("mount contains unsupported options")
                mount_type = str(item.get("type") or "volume")
                source = item.get("source")
                target = str(item.get("target") or "")
                if mount_type == "volume":
                    if source and str(source) not in declared_volumes:
                        raise PolicyError(
                            "named volume must be declared by this project"
                        )
                elif mount_type != "tmpfs":
                    raise PolicyError("only named volumes and tmpfs mounts are allowed")
            else:
                text = str(item)
                parts = text.split(":")
                if len(parts) == 1:
                    source = None
                    target = parts[0]
                else:
                    source = parts[0]
                    target = parts[1]
                if source and source not in declared_volumes:
                    raise PolicyError("only declared named volumes are allowed")
            if not target.startswith("/") or target.endswith(".sock"):
                raise PolicyError("invalid mount destination")

    @staticmethod
    def _validate_network_references(value: Any, declared_networks: set[str]) -> None:
        if value is None:
            return
        if isinstance(value, Mapping):
            names = value.keys()
            for config in value.values():
                if config not in (None, {}) and (
                    not isinstance(config, Mapping) or set(config) - {"aliases"}
                ):
                    raise PolicyError("network attachment contains unsupported options")
        elif isinstance(value, list):
            names = value
        else:
            raise PolicyError("networks must be a mapping or list")
        for name in names:
            if str(name) != "default" and str(name) not in declared_networks:
                raise PolicyError("service references an undeclared network")

    @staticmethod
    def _validate_dependencies(value: Any, declared_services: set[str]) -> None:
        if value is None:
            return
        if isinstance(value, Mapping):
            names = value.keys()
            for config in value.values():
                if config not in (None, {}) and (
                    not isinstance(config, Mapping)
                    or set(config) - {"condition", "required", "restart"}
                ):
                    raise PolicyError("dependency contains unsupported options")
        elif isinstance(value, list):
            names = value
        else:
            raise PolicyError("depends_on must be a mapping or list")
        if any(str(name) not in declared_services for name in names):
            raise PolicyError("dependency references an unknown service")

    @staticmethod
    def _validate_profiles(value: Any) -> None:
        for profile in ComposePolicy._as_list(value, maximum=20):
            if not _SAFE_NAME.fullmatch(str(profile)):
                raise PolicyError("invalid Compose profile")

    @staticmethod
    def _validate_restart(value: Any) -> None:
        restart = str(value or "no")
        if restart == "no":
            return
        match = re.fullmatch(r"on-failure(?::([0-9]+))?", restart)
        if not match or (match.group(1) and int(match.group(1)) > 10):
            raise PolicyError("restart policy must be no or bounded on-failure")

    @staticmethod
    def _validate_healthcheck(value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, Mapping):
            raise PolicyError("healthcheck must be a mapping")
        if set(value) - {
            "test",
            "interval",
            "timeout",
            "retries",
            "start_period",
            "start_interval",
            "disable",
        }:
            raise PolicyError("healthcheck contains unsupported options")
        retries = value.get("retries")
        if retries is not None and (
            not isinstance(retries, int) or not 1 <= retries <= 10
        ):
            raise PolicyError("healthcheck retries exceed policy")
        test = value.get("test")
        if isinstance(test, list):
            if len(test) > 20 or any(len(str(item)) > 1024 for item in test):
                raise PolicyError("healthcheck command exceeds policy")
        elif test is not None and len(str(test)) > 8192:
            raise PolicyError("healthcheck command exceeds policy")
        for key, maximum in (
            ("interval", 300),
            ("timeout", 60),
            ("start_period", 300),
            ("start_interval", 300),
        ):
            ComposePolicy._validate_duration(value.get(key), maximum_seconds=maximum)

    @staticmethod
    def _validate_duration(value: Any, *, maximum_seconds: float) -> None:
        if value is None:
            return
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(ms|s|m)", str(value))
        if not match:
            raise PolicyError("duration is outside the supported policy format")
        multiplier = {"ms": 0.001, "s": 1.0, "m": 60.0}[match.group(2)]
        seconds = float(match.group(1)) * multiplier
        if seconds <= 0 or seconds > maximum_seconds:
            raise PolicyError("duration exceeds policy")

    @staticmethod
    def _validate_size(value: Any, *, maximum: int) -> None:
        if value is None:
            return
        match = re.fullmatch(r"([0-9]+)([kKmMgG])?", str(value))
        if not match:
            raise PolicyError("size is outside the supported policy format")
        multiplier = {
            None: 1,
            "k": 1024,
            "m": 1024**2,
            "g": 1024**3,
        }[match.group(2).lower() if match.group(2) else None]
        if int(match.group(1)) * multiplier > maximum:
            raise PolicyError("size exceeds policy")

    @staticmethod
    def _resolve_project_source(
        project_directory: Path,
        raw: str,
        *,
        require_directory: bool = False,
    ) -> Path:
        candidate = Path(raw).expanduser()
        if candidate.is_absolute() or ".." in candidate.parts:
            raise PolicyError("build source must be relative to the project directory")
        candidate = project_directory / candidate
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise PolicyError("build source path is unavailable") from exc
        if not resolved.is_relative_to(project_directory):
            raise PolicyError("build source escapes the project directory")
        if require_directory and not resolved.is_dir():
            raise PolicyError("build context must be a directory")
        return resolved

    @staticmethod
    def _as_list(value: Any, *, maximum: int) -> list[Any]:
        if value is None:
            return []
        result = value if isinstance(value, list) else [value]
        if len(result) > maximum:
            raise PolicyError("compose list exceeds policy limit")
        return result

    @staticmethod
    def _service_summary(name: str, service: Mapping[str, Any]) -> ServiceSummary:
        ports: list[str] = []
        for item in ComposePolicy._as_list(service.get("ports"), maximum=64):
            if isinstance(item, Mapping):
                ports.append(
                    f"{item.get('host_ip')}:{item.get('published')}:{item.get('target')}"
                )
            else:
                ports.append(str(item))
        return ServiceSummary(
            name=name,
            image=str(service["image"]) if service.get("image") else None,
            build="build" in service,
            published_ports=ports,
        )
