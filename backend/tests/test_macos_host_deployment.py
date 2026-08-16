"""Static release gates for the macOS host-executor deployment boundary.

These tests inspect configuration only. They must never install, start, confirm, cancel,
or execute a host operation.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "start_image_pipeline.sh"
BOTTOM_LOCK_LAUNCHER = ROOT / "bttm_lock_start.command"
BROKER_MODELS = ROOT / "docker-broker" / "src" / "docker_broker" / "models.py"
BROKER_API = ROOT / "docker-broker" / "src" / "docker_broker" / "api.py"
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
    assert (
        executor.index('chmod u+w "$staged"')
        < executor.index('mv "$staged" "$HOST_EXECUTOR_RUNTIME"')
        < executor.index('chmod a-w "$HOST_EXECUTOR_RUNTIME"')
    )
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


def test_launcher_has_isolated_docker_broker_lifecycle() -> None:
    launcher = _text(LAUNCHER)
    broker = _section(
        launcher,
        "# ── optional Docker broker",
        "# ── langgraph",
    )

    assert "DOCKER_BROKER_PORT=8766" in launcher
    assert 'DOCKER_BROKER_ROOT="$HOME/.jasper/docker-broker"' in launcher
    assert 'DOCKER_BROKER_RUNTIME="$DOCKER_BROKER_ROOT/runtime"' in launcher
    assert 'DOCKER_BROKER_PRIVATE="$DOCKER_BROKER_ROOT/private"' in launcher
    assert 'DOCKER_BROKER_DOCKER="/usr/local/bin/docker"' in launcher
    assert (
        'DOCKER_BROKER_ALLOWED_ROOT="${DOCKER_BROKER_ALLOWED_ROOT:-$ROOT}"' in launcher
    )
    assert 'DOCKER_BROKER_AGENT_SERVER="http://127.0.0.1:8123"' in launcher
    assert 'DOCKER_BROKER_OWNER="local-owner-v1"' in launcher
    assert "DOCKER_BROKER_LEASE_SECONDS=14400" in launcher
    assert "install-docker-broker)" in launcher
    assert "Type INSTALL to continue" in broker
    assert 'ditto --noqtn "$ROOT/docker-broker"' in broker
    assert '"$DOCKER_BROKER_BOOTSTRAP_PYTHON" -m venv "$staged/venv"' in broker
    assert "integrity.sha256" in broker
    assert "-exec /usr/bin/shasum -a 256 {} +" in broker
    assert (
        broker.index('chmod u+w "$staged"')
        < broker.index('mv "$staged" "$DOCKER_BROKER_RUNTIME"')
        < broker.rindex('chmod a-w "$DOCKER_BROKER_RUNTIME"')
    )
    assert 'chmod u+w "$DOCKER_BROKER_RUNTIME"' in broker
    assert "runtime swap failed; restoring the previous snapshot" in broker
    assert 'chmod 700 "$DOCKER_BROKER_ROOT" "$DOCKER_BROKER_PRIVATE"' in broker
    assert 'chmod 600 "$DOCKER_BROKER_LOG"' in broker
    for private_dir in ("state", "run", "logs", "tmp", "home"):
        assert f'"$DOCKER_BROKER_PRIVATE/{private_dir}"' in broker
    assert "env -i" in broker
    assert 'HOME="$DOCKER_BROKER_PRIVATE/home"' in broker
    assert "--host 127.0.0.1 --port" in broker
    assert '--allowed-root "$DOCKER_BROKER_ALLOWED_ROOT"' in broker
    assert "--allowed-root $DOCKER_BROKER_ALLOWED_ROOT" in broker
    assert '--state-directory "$DOCKER_BROKER_STATE"' in broker
    assert '--docker-path "$DOCKER_BROKER_DOCKER"' in broker
    assert '--agent-server-url "$DOCKER_BROKER_AGENT_SERVER"' in broker
    assert '--owner-id "$DOCKER_BROKER_OWNER"' in broker
    assert '--lease-seconds "$DOCKER_BROKER_LEASE_SECONDS" --allow-builds' in broker
    assert 'ps -p "$pid" -o command=' in broker
    assert '"http://127.0.0.1:$DOCKER_BROKER_PORT/health"' in broker
    assert '"service"[[:space:]]*:[[:space:]]*"docker-broker"' in broker
    assert "Installed Docker broker failed health checks" in broker

    # Broker lifecycle must only signal the PID whose complete command matches.
    for forbidden in ("pkill", "killall", "xargs kill", "lsof -ti"):
        assert forbidden not in broker

    start_case = _section(launcher, "  start)", "  stop)")
    assert (
        start_case.index("start_langgraph")
        < start_case.index("start_docker_broker")
        < start_case.index("start_host_executor")
    )
    assert "if ! start_docker_broker" in start_case
    assert "stop_docker_broker" in start_case

    stop_case = _section(launcher, "  stop)", "  status)")
    assert (
        stop_case.index("stop_host_executor")
        < stop_case.index("stop_docker_broker")
        < stop_case.index("stop_langgraph")
    )
    assert "status_docker_broker || true" in launcher

    restart_core = _section(launcher, "  restart-core)", "  install-host-executor)")
    assert (
        restart_core.index("stop_host_executor")
        < restart_core.index("stop_docker_broker")
        < restart_core.index("stop_langgraph")
    )
    assert (
        restart_core.index("start_langgraph")
        < restart_core.index("start_docker_broker")
        < restart_core.index("start_host_executor")
    )

    assert (
        'frontend_docker_broker_url="http://127.0.0.1:'
        '$DOCKER_BROKER_PORT/v1/coder/confirmations"'
    ) in launcher
    assert 'NEXT_PUBLIC_DOCKER_BROKER_URL="$frontend_docker_broker_url"' in launcher
    assert "docker_broker=$frontend_docker_broker_url" in launcher
    assert "install-docker-broker}" in launcher

    broker_models = _text(BROKER_MODELS)
    broker_api = _text(BROKER_API)
    assert 'service: Literal["docker-broker"]' in broker_models
    assert 'service="docker-broker"' in broker_api


def test_bottom_locking_hands_original_workspace_to_broker() -> None:
    launcher = _text(BOTTOM_LOCK_LAUNCHER)
    assert 'RUNTIME_ROOT="${ROOT}-bottom-locking-runtime"' in launcher
    assert 'export DOCKER_BROKER_ALLOWED_ROOT="$ROOT"' in launcher
    assert launcher.index('export DOCKER_BROKER_ALLOWED_ROOT="$ROOT"') < launcher.index(
        '"$RUNTIME_ROOT/start_image_pipeline.sh" restart-core'
    )
    assert (
        launcher.count(
            'NEXT_PUBLIC_DOCKER_BROKER_URL="http://127.0.0.1:8766/v1/coder/confirmations"'
        )
        == 2
    )


def test_compose_exposes_receipt_verification_only_and_masks_credentials() -> None:
    compose = _text(COMPOSE)

    assert (
        "${HOME}/.jasper/macos-host-executor/public:/run/macos-host-executor:ro"
    ) in compose
    assert "MACOS_HOST_EXECUTOR_URL=http://host.docker.internal:8765" in compose
    assert (
        "MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE="
        "/run/macos-host-executor/receipt-signing.pub"
    ) in compose
    # The container receives only the broker's non-secret HTTP location. Broker
    # credentials, lease material, private state, and Docker authority stay native.
    assert "DOCKER_BROKER_URL=http://host.docker.internal:8766" in compose

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
        "docker-broker/private",
        "docker-broker/state",
        "DOCKER_BROKER_CLIENT_SECRET",
        "DOCKER_BROKER_TOKEN",
        "DOCKER_BROKER_LEASE",
        "X-Broker-Client-Secret",
        "Authorization: Bearer",
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
    assert policy["sandbox_workspace_roots"] == []
    assert policy["sbx_executable"] is None
    assert policy["sbx_home"] is None


def test_executor_policy_has_no_arbitrary_github_shell_docker_or_privilege_route() -> (
    None
):
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
    # The sole Docker spelling is the policy-built inner Compose argv; callers
    # cannot provide a command, executable, argv, environment, or sandbox name.
    assert policy_source.count('            "docker",') == 1
    assert '            "compose",' in policy_source
    assert (
        '"run",\n                "shell",\n                "--name",' in policy_source
    )
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
