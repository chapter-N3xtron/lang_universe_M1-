"""Independent category policies and fixed argv construction."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .errors import PolicyDeniedError
from .models import (
    ApplicationInstallAction,
    DownloadAction,
    HomebrewAction,
    HostInspectionAction,
    HostOperationPlan,
    NativeApplicationAction,
    Sha256,
)
from .security import (
    canonical_configured_executable,
    canonical_destination_absent,
    canonical_existing,
    reject_command_like_text,
    verify_hash,
)


class PolicyConfig(BaseModel):
    """Trusted local policy. Empty allowlists are secure deny-all defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    inspection_roots: tuple[str, ...] = ()
    download_roots: tuple[str, ...] = ()
    artifact_roots: tuple[str, ...] = ()
    application_roots: tuple[str, ...] = ()
    working_roots: tuple[str, ...] = ()
    output_roots: tuple[str, ...] = ()
    allowed_download_domains: tuple[str, ...] = ()
    allowed_formulae: tuple[str, ...] = ()
    allowed_casks: tuple[str, ...] = ()
    allowed_applications: dict[str, str] = Field(default_factory=dict)
    allowed_application_team_ids: dict[str, str] = Field(default_factory=dict)
    allowed_native_script_hashes: tuple[Sha256, ...] = ()
    homebrew_executable: str | None = None


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    category: str
    executable: str
    argv: tuple[str, ...]
    working_directory: str | None = None
    approved_paths: tuple[str, ...] = ()
    rollback_strategy: str = "none"


class ActionPolicy:
    def __init__(self, config: PolicyConfig):
        self.config = config

    def plan(self, operation: HostOperationPlan) -> ExecutionPlan:
        action = operation.action
        if isinstance(action, HostInspectionAction):
            plan = self._inspection(action)
        elif isinstance(action, DownloadAction):
            plan = self._download(action)
        elif isinstance(action, HomebrewAction):
            plan = self._homebrew(action)
        elif isinstance(action, ApplicationInstallAction):
            plan = self._application(action)
        elif isinstance(action, NativeApplicationAction):
            plan = self._native(action)
        else:
            raise PolicyDeniedError("unknown action category")
        self._validate_mutations_and_rollback(operation, plan)
        return plan.model_copy(
            update={"rollback_strategy": operation.rollback.strategy}
        )

    @staticmethod
    def _validate_mutations_and_rollback(
        operation: HostOperationPlan, plan: ExecutionPlan
    ) -> None:
        action = operation.action
        required_path: str | None = None
        if isinstance(action, (DownloadAction, ApplicationInstallAction)) or (
            isinstance(action, NativeApplicationAction)
            and action.operation == "blender_background_render"
        ):
            required_path = plan.approved_paths[-1]
        if required_path:
            declared = tuple(
                mutation.path
                for mutation in operation.expected_mutations
                if mutation.operation == "create"
            )
            if declared != (required_path,) or len(operation.expected_mutations) != 1:
                raise PolicyDeniedError(
                    "expected mutations must exactly declare the created destination"
                )
        elif isinstance(action, HomebrewAction) and not operation.expected_mutations:
            raise PolicyDeniedError("Homebrew operations require explicit mutations")
        elif not isinstance(action, HomebrewAction) and any(
            mutation.operation != "inspect" for mutation in operation.expected_mutations
        ):
            raise PolicyDeniedError("read-only action declares a mutation")
        if isinstance(action, (DownloadAction, ApplicationInstallAction)):
            if operation.rollback.strategy != "remove_created_destination":
                raise PolicyDeniedError(
                    "download and application copy require destination-only rollback"
                )
        elif (
            operation.rollback.strategy == "remove_created_destination"
            and not isinstance(action, DownloadAction | ApplicationInstallAction)
        ):
            raise PolicyDeniedError(
                "adapter cannot honor the requested rollback strategy"
            )

    def revalidate(self, operation: HostOperationPlan) -> None:
        action = operation.action
        if isinstance(action, ApplicationInstallAction):
            artifact = canonical_existing(
                action.artifact_path, self.config.artifact_roots, regular_file=True
            )
            verify_hash(artifact, action.artifact_sha256)
        if isinstance(action, NativeApplicationAction):
            if action.operation == "blender_background_render":
                canonical_existing(
                    action.input_path or "",
                    self.config.working_roots,
                    regular_file=True,
                )
                canonical_destination_absent(
                    action.output_path or "", self.config.output_roots
                )
            if action.script:
                script = canonical_existing(
                    action.script.path, self.config.working_roots, regular_file=True
                )
                verify_hash(script, action.script.sha256)
            for item in action.configuration:
                config = canonical_existing(
                    item.path, self.config.working_roots, regular_file=True
                )
                verify_hash(config, item.sha256)

    def _inspection(self, action: HostInspectionAction) -> ExecutionPlan:
        paths: tuple[str, ...] = ()
        if action.target_path:
            paths = (
                str(
                    canonical_existing(action.target_path, self.config.inspection_roots)
                ),
            )
        if action.application_id:
            app = self.config.allowed_applications.get(action.application_id)
            if not app:
                raise PolicyDeniedError("application is not allowlisted")
            bundle = next(
                (
                    parent
                    for parent in (Path(app), *Path(app).parents)
                    if parent.suffix == ".app"
                ),
                None,
            )
            if not bundle:
                raise PolicyDeniedError(
                    "allowlisted executable is not inside an app bundle"
                )
            paths = (
                str(canonical_existing(str(bundle), self.config.application_roots)),
            )
        executable, argv = {
            "macos_version": ("/usr/bin/sw_vers", ("/usr/bin/sw_vers",)),
            "architecture": ("/usr/bin/uname", ("/usr/bin/uname", "-m")),
            "disk_space": ("builtin:statvfs", ("statvfs", *paths)),
            "path_metadata": ("builtin:path_metadata", ("path_metadata", *paths)),
            "application_presence": (
                "builtin:application_presence",
                ("application_presence", *paths),
            ),
            "application_version": (
                "builtin:application_version",
                ("application_version", *paths),
            ),
        }[action.query]
        return ExecutionPlan(
            category=action.category,
            executable=executable,
            argv=argv,
            approved_paths=paths,
        )

    def _download(self, action: DownloadAction) -> ExecutionPlan:
        host = (urlsplit(action.url).hostname or "").lower()
        if host not in {item.lower() for item in self.config.allowed_download_domains}:
            raise PolicyDeniedError("download domain is not exactly allowlisted")
        destination = canonical_destination_absent(
            action.destination, self.config.download_roots
        )
        return ExecutionPlan(
            category=action.category,
            executable="builtin:https",
            argv=("GET", action.url),
            approved_paths=(str(destination),),
        )

    def _homebrew(self, action: HomebrewAction) -> ExecutionPlan:
        allowed = (
            self.config.allowed_formulae
            if action.package_kind == "formula"
            else self.config.allowed_casks
        )
        if action.package not in allowed or not self.config.homebrew_executable:
            raise PolicyDeniedError("Homebrew package or executable is not allowlisted")
        reject_command_like_text((action.package,))
        executable = str(
            canonical_configured_executable(
                self.config.homebrew_executable, (self.config.homebrew_executable,)
            )
        )
        flag = "--formula" if action.package_kind == "formula" else "--cask"
        argv = (executable, action.operation, flag, action.package)
        return ExecutionPlan(
            category=action.category,
            executable=executable,
            argv=argv,
        )

    def _application(self, action: ApplicationInstallAction) -> ExecutionPlan:
        if action.application_id not in self.config.allowed_applications:
            raise PolicyDeniedError("application identity is not allowlisted")
        trusted_team_id = self.config.allowed_application_team_ids.get(
            action.application_id
        )
        if not trusted_team_id or action.require_team_id != trusted_team_id:
            raise PolicyDeniedError(
                "requested application Team ID does not match trusted policy"
            )
        artifact = canonical_existing(
            action.artifact_path, self.config.artifact_roots, regular_file=True
        )
        verify_hash(artifact, action.artifact_sha256)
        destination = canonical_destination_absent(
            action.destination, self.config.application_roots
        )
        return ExecutionPlan(
            category=action.category,
            executable="builtin:application_installer",
            argv=(action.mode, action.artifact_kind, action.application_id),
            approved_paths=(str(artifact), str(destination)),
        )

    def _native(self, action: NativeApplicationAction) -> ExecutionPlan:
        configured = self.config.allowed_applications.get(action.application_id)
        if not configured:
            raise PolicyDeniedError("native application is not allowlisted")
        executable = str(
            canonical_configured_executable(
                configured, self.config.allowed_applications.values()
            )
        )
        work = canonical_existing(action.working_directory, self.config.working_roots)
        paths = [str(work)]
        if action.operation == "blender_version":
            argv = (executable, "--background", "--version")
        else:
            input_path = canonical_existing(
                action.input_path or "", self.config.working_roots, regular_file=True
            )
            output_path = canonical_destination_absent(
                action.output_path or "", self.config.output_roots
            )
            argv_list = [
                executable,
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                str(input_path),
            ]
            if action.script:
                script = canonical_existing(
                    action.script.path, self.config.working_roots, regular_file=True
                )
                verify_hash(script, action.script.sha256)
                if action.script.sha256 not in self.config.allowed_native_script_hashes:
                    raise PolicyDeniedError("native script hash is not operator-allowlisted")
                if script.suffix != ".py":
                    raise PolicyDeniedError(
                        "Blender script must be an approval-bound .py file"
                    )
                argv_list.extend(("--python", str(script)))
                paths.append(str(script))
            argv_list.extend(("--render-output", str(output_path), "--render-anim"))
            argv = tuple(argv_list)
            paths.extend((str(input_path), str(output_path)))
        self.revalidate_request_hashes(action)
        return ExecutionPlan(
            category=action.category,
            executable=executable,
            argv=argv,
            working_directory=str(work),
            approved_paths=tuple(paths),
        )

    def revalidate_request_hashes(self, action: NativeApplicationAction) -> None:
        for item in action.configuration:
            path = canonical_existing(
                item.path, self.config.working_roots, regular_file=True
            )
            verify_hash(path, item.sha256)
