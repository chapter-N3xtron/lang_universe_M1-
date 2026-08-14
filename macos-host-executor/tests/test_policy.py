from __future__ import annotations

from pathlib import Path

import pytest
from conftest import hash_file

from macos_host_executor.errors import InputChangedError, PolicyDeniedError
from macos_host_executor.models import HostOperationPlan
from macos_host_executor.policy import ActionPolicy, PolicyConfig


def request(action: dict, mutations: list | None = None) -> HostOperationPlan:
    destination = action.get("destination") or action.get("output_path")
    if mutations is None and destination:
        mutations = [
            {"operation": "create", "path": destination, "detail": "declared output"}
        ]
    if mutations is None and action["category"] == "homebrew":
        mutations = [
            {
                "operation": "replace",
                "path": "/opt/homebrew",
                "detail": "package manager state",
            }
        ]
    rollback = (
        "remove_created_destination"
        if action["category"] in {"https_download", "application_install"}
        else "none"
    )
    return HostOperationPlan.model_validate(
        {
            "action": action,
            "expected_mutations": tuple(mutations or []),
            "timeout_seconds": 30,
            "rollback": {
                "strategy": rollback,
                "removes_only_request_created_paths": True,
                "may_require_human_inspection": True,
            },
            "expiry_seconds": 300,
        }
    )


def configured(roots: dict[str, Path]) -> ActionPolicy:
    blender = roots["applications"] / "Blender.app" / "Contents" / "MacOS"
    blender.mkdir(parents=True)
    executable = blender / "Blender"
    executable.write_bytes(b"fake executable identity")
    executable.chmod(0o700)
    brew = roots["work"] / "brew"
    brew.write_bytes(b"fake Homebrew identity")
    brew.chmod(0o700)
    return ActionPolicy(
        PolicyConfig(
            inspection_roots=(str(roots["inspect"]),),
            download_roots=(str(roots["downloads"]),),
            artifact_roots=(str(roots["artifacts"]),),
            application_roots=(str(roots["applications"]),),
            working_roots=(str(roots["work"]),),
            output_roots=(str(roots["output"]),),
            allowed_download_domains=("download.blender.org",),
            allowed_formulae=("ffmpeg",),
            allowed_casks=("blender",),
            allowed_applications={"org.blender.Blender": str(executable)},
            allowed_application_team_ids={"org.blender.Blender": "JCKZK6G8RJ"},
            homebrew_executable=str(brew),
        )
    )


def test_category_specific_fixed_plans(roots: dict[str, Path]) -> None:
    policy = configured(roots)
    download = policy.plan(
        request(
            {
                "category": "https_download",
                "url": "https://download.blender.org/release.dmg",
                "destination": str(roots["downloads"] / "release.dmg"),
                "sha256": "a" * 64,
                "max_bytes": 100,
            }
        )
    )
    assert download.executable == "builtin:https"
    brew = policy.plan(
        request(
            {
                "category": "homebrew",
                "operation": "install",
                "package_kind": "cask",
                "package": "blender",
            }
        )
    )
    assert brew.argv[1:] == ("install", "--cask", "blender")
    assert brew.executable == str(roots["work"] / "brew")
    inspect = policy.plan(
        request({"category": "host_inspection", "query": "architecture"})
    )
    assert inspect.argv == ("/usr/bin/uname", "-m")


def test_download_domain_and_homebrew_are_exact_allowlists(
    roots: dict[str, Path],
) -> None:
    policy = configured(roots)
    with pytest.raises(PolicyDeniedError):
        policy.plan(
            request(
                {
                    "category": "https_download",
                    "url": "https://evil.example/x",
                    "destination": str(roots["downloads"] / "x"),
                    "sha256": "a" * 64,
                    "max_bytes": 10,
                }
            )
        )
    with pytest.raises(PolicyDeniedError):
        policy.plan(
            request(
                {
                    "category": "homebrew",
                    "operation": "install",
                    "package_kind": "cask",
                    "package": "unknown",
                }
            )
        )


def test_application_and_blender_inputs_are_hash_bound(roots: dict[str, Path]) -> None:
    policy = configured(roots)
    artifact = roots["artifacts"] / "Blender.dmg"
    digest = hash_file(artifact)
    app_request = request(
        {
            "category": "application_install",
            "artifact_path": str(artifact),
            "artifact_sha256": digest,
            "artifact_kind": "dmg",
            "application_id": "org.blender.Blender",
            "destination": str(roots["applications"] / "Installed.app"),
            "mode": "stage",
            "require_team_id": "JCKZK6G8RJ",
        }
    )
    assert policy.plan(app_request).executable == "builtin:application_installer"
    mismatched = app_request.model_copy(
        update={
            "action": app_request.action.model_copy(
                update={"require_team_id": "ATTACKER123"}
            )
        }
    )
    with pytest.raises(PolicyDeniedError, match="Team ID"):
        policy.plan(mismatched)
    artifact.write_bytes(b"race")
    with pytest.raises(InputChangedError):
        policy.revalidate(app_request)

    scene = roots["work"] / "scene.blend"
    scene.write_bytes(b"scene")
    script = roots["work"] / "render.py"
    script_hash = hash_file(script)
    policy = ActionPolicy(
        policy.config.model_copy(
            update={"allowed_native_script_hashes": (script_hash,)}
        )
    )
    native = request(
        {
            "category": "native_application",
            "application_id": "org.blender.Blender",
            "operation": "blender_background_render",
            "working_directory": str(roots["work"]),
            "input_path": str(scene),
            "output_path": str(roots["output"] / "render.png"),
            "script": {"path": str(script), "sha256": script_hash},
        }
    )
    denied_policy = ActionPolicy(
        policy.config.model_copy(update={"allowed_native_script_hashes": ()})
    )
    with pytest.raises(PolicyDeniedError, match="script hash"):
        denied_policy.plan(native)

    plan = policy.plan(native)
    assert "--python" in plan.argv and "--render-anim" in plan.argv
    assert "--factory-startup" in plan.argv and "--disable-autoexec" in plan.argv
