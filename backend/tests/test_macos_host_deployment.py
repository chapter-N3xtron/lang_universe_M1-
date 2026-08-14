"""Static release gates for the macOS host-executor deployment boundary.

These tests inspect configuration only. They must never install, start, confirm, cancel,
or execute a host operation.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "start_image_pipeline.sh"
COMPOSE = ROOT / "backend" / "docker-compose.override.yml"
POLICY = ROOT / "macos-host-executor" / "policy.example.json"
EXECUTOR_POLICY = (
    ROOT / "macos-host-executor" / "src" / "macos_host_executor" / "policy.py"
)
EXECUTOR_RUNNER = (
    ROOT / "macos-host-executor" / "src" / "macos_host_executor" / "runner.py"
)
SECURITY = ROOT / "backend" / "SECURITY.md"
PERSISTENCE = ROOT / "backend" / "PERSISTENCE.md"
RUNBOOK = ROOT / "macos-host-executor" / "README.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_launcher_has_explicit_isolated_fail_closed_lifecycle() -> None:
    launcher = _text(LAUNCHER)
    executor = _section(
        launcher,
        "# ── optional macOS host executor",
        "# ── langgraph",
    )

    assert "umask 077" in launcher
    assert 'HOST_EXECUTOR_ROOT="$HOME/.jasper/macos-host-executor"' in launcher
    assert "install-host-executor)" in launcher
    assert "Type INSTALL to continue" in executor
    assert 'ditto --noqtn "$ROOT/macos-host-executor"' in executor
    assert '"$HOST_EXECUTOR_BOOTSTRAP_PYTHON" -m venv "$staged/venv"' in executor
    assert "Python 3.11 or newer is required" in executor
    assert "xcrun swift build -c release" in executor
    assert "integrity.sha256" in executor
    assert "-exec /usr/bin/shasum -a 256 {} +" in executor
    assert executor.index('chmod u+w "$staged"') < executor.index(
        'mv "$staged" "$HOST_EXECUTOR_RUNTIME"'
    ) < executor.index('chmod a-w "$HOST_EXECUTOR_RUNTIME"')
    assert 'chmod 700 "$HOST_EXECUTOR_ROOT"' in executor
    assert 'chmod 600 "$HOST_EXECUTOR_POLICY"' in executor
    assert 'chmod 755 "$HOST_EXECUTOR_PUBLIC"' in executor
    assert "env -i" in executor
    assert 'HOME="$HOST_EXECUTOR_PRIVATE/home"' in executor
    assert "--host 127.0.0.1 --port" in executor
    assert '--agent-server-url "$HOST_EXECUTOR_AGENT_SERVER"' in executor
    assert 'HOST_EXECUTOR_AGENT_SERVER="http://127.0.0.1:8123"' in launcher
    assert '"http://127.0.0.1:$HOST_EXECUTOR_PORT/health"' in executor
    assert 'ps -p "$pid" -o command=' in executor
    assert "Installed host executor failed health checks" in executor
    assert "No host operation or canary was run" in executor
    assert 'frontend_api_url="http://127.0.0.1:$LANGGRAPH_PORT"' in launcher
    assert 'NEXT_PUBLIC_API_URL="$frontend_api_url"' in launcher
    assert ".next/.jasper-runtime-config" in launcher

    # Executor lifecycle must never use a broad process or port kill.
    for forbidden in ("pkill", "killall", "xargs kill", "lsof -ti"):
        assert forbidden not in executor

    start_case = _section(launcher, "  start)", "  stop)")
    assert start_case.index("start_langgraph") < start_case.index("start_host_executor")
    assert start_case.index("start_host_executor") < start_case.index("start_backend")
    assert "if ! start_host_executor" in start_case
    assert "stop_langgraph" in start_case

    restart_core = _section(launcher, "  restart-core)", "  install-host-executor)")
    assert "stop_host_executor" in restart_core
    assert "if ! start_host_executor" in restart_core


def test_compose_exposes_receipt_verification_only_and_masks_credentials() -> None:
    compose = _text(COMPOSE)

    assert (
        "${HOME}/.jasper/macos-host-executor/public:"
        "/run/macos-host-executor:ro"
    ) in compose
    assert "MACOS_HOST_EXECUTOR_URL=http://host.docker.internal:8765" in compose
    assert (
        "MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE="
        "/run/macos-host-executor/receipt-signing.pub"
    ) in compose

    for masked in (
        "${HOME}/.jasper",
        "${HOME}/Library/Keychains",
        "${HOME}/.ssh",
        "${HOME}/.aws",
        "${HOME}/.gnupg",
        "${HOME}/.config/gh",
        "${HOME}/.docker",
        "${HOME}/.kube",
        "${HOME}/.azure",
        "${HOME}/.config/gcloud",
    ):
        assert f"- {masked}" in compose

    # Public verification data and a GET-only endpoint are the complete bridge.
    for forbidden in (
        "private/state",
        "private/config",
        "private_key",
        "signing.key",
        "control.sock",
        "docker.sock",
        "SSH_AUTH_SOCK",
        "GITHUB_TOKEN",
        "GH_TOKEN",
    ):
        assert forbidden not in compose


def test_example_policy_is_explicit_and_denies_unpinned_app_install() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    for roots in (
        "inspection_roots",
        "download_roots",
        "artifact_roots",
        "application_roots",
        "working_roots",
        "output_roots",
    ):
        assert policy[roots]
        assert all(Path(item).is_absolute() for item in policy[roots])

    assert policy["allowed_download_domains"] == ["download.blender.org"]
    assert policy["allowed_formulae"] == []
    assert policy["allowed_casks"] == ["blender"]
    assert policy["homebrew_executable"] == "/opt/homebrew/bin/brew"
    assert policy["allowed_applications"] == {
        "blender": "/Applications/Blender.app/Contents/MacOS/Blender"
    }
    # Application copy/install and native scripts require separate operator pins.
    assert policy["allowed_application_team_ids"] == {}
    assert policy["allowed_native_script_hashes"] == []


def test_executor_policy_has_no_github_shell_persistence_or_privilege_route() -> None:
    policy_source = _text(EXECUTOR_POLICY)
    runner_source = _text(EXECUTOR_RUNNER)

    # The policy layer constructs the complete executable/argv plan. It must not
    # acquire a route to these capabilities, even if a caller asks for one.
    for forbidden_literal in (
        '"/bin/sh"',
        '"/bin/bash"',
        '"/usr/bin/sudo"',
        '"sudo"',
        '"gh"',
        '"git"',
        '"ssh"',
        '"docker"',
        '"launchctl"',
        '"osascript"',
        '"security"',
    ):
        assert forbidden_literal not in policy_source

    assert "subprocess" not in policy_source
    assert '"/usr/bin/sw_vers"' in policy_source
    assert '"/usr/bin/uname"' in policy_source
    assert '"builtin:https"' in policy_source
    assert '"builtin:application_installer"' in policy_source
    assert "shell=False" in runner_source
    assert "start_new_session=True" in runner_source
    assert "close_fds=True" in runner_source
    assert "os.killpg(process.pid" in runner_source


def test_hybrid_security_persistence_and_operator_runbook_are_documented() -> None:
    security = _text(SECURITY)
    persistence = _text(PERSISTENCE)
    runbook = _text(RUNBOOK)
    docs = "\n".join((security, persistence, runbook)).lower()

    for required in (
        "three security and restart domains",
        "linux-container",
        "native confirmation",
        "single-use",
        "rollback/disable",
        "policy.json",
        "no github overlap",
        "automatic privilege escalation",
        "keychain",
        "touch id",
    ):
        assert required in docs

    assert "ordinary `start`, `restart`, and `restart-core` never" in runbook.lower()
    assert "does not start the executor" in runbook
    assert "never repeats a mutation" in persistence
