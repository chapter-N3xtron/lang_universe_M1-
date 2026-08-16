"""Production CLI for the explicitly configured, loopback-only executor."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .adapters import (
    ApplicationAdapter,
    DockerSandboxAdapter,
    DownloadAdapter,
    HomebrewAdapter,
    InspectionAdapter,
    NativeApplicationAdapter,
)
from .api import create_app, require_loopback_bind
from .configuration import ConfigurationError, load_production_configuration
from .core import ExecutorCore
from .runner import SubprocessRunner
from .signing import ReceiptSigner
from .state import StateStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Policy-limited macOS host executor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--policy-json", type=Path)
    parser.add_argument("--agent-server-url")
    parser.add_argument("--confirmation-helper", type=Path)
    parser.add_argument("--state-directory", type=Path)
    parser.add_argument("--public-key-output", type=Path)
    args = parser.parse_args()
    require_loopback_bind(args.host)
    try:
        config = load_production_configuration(
            policy_json=args.policy_json,
            agent_server_url=args.agent_server_url,
            confirmation_helper=args.confirmation_helper,
            state_directory=args.state_directory,
        )
    except ConfigurationError as exc:
        parser.error(str(exc))

    state = config.state_directory
    policy_config = config.policy.config
    canonical_sbx_home: Path | None = None
    if policy_config.sbx_home:
        sbx_home = Path(policy_config.sbx_home)
        try:
            canonical_sbx_home = sbx_home.resolve(strict=True)
        except OSError as exc:
            parser.error(f"configured SBX operator home is unavailable: {exc}")
        if (
            not sbx_home.is_absolute()
            or canonical_sbx_home != sbx_home
            or not canonical_sbx_home.is_dir()
        ):
            parser.error("configured SBX operator home must be a canonical directory")

    signer = ReceiptSigner.load_or_create(state / "receipt-signing.key")
    signer.export_public_key(
        (args.public_key_output or state / "receipt-signing.pub").expanduser()
    )
    runtime_home = state / "runtime-home"
    runtime_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    runner = SubprocessRunner(
        state / "staging" / "processes",
        trusted_environment={"HOME": str(runtime_home)},
    )
    sbx_runner = runner
    if canonical_sbx_home is not None:
        sbx_runner = SubprocessRunner(
            state / "staging" / "sbx-processes",
            trusted_environment={"HOME": str(canonical_sbx_home)},
        )
    adapters = {
        "host_inspection": InspectionAdapter(runner),
        "https_download": DownloadAdapter(
            state / "staging" / "downloads", policy_config.allowed_download_domains
        ),
        "homebrew": HomebrewAdapter(runner),
        "application_install": ApplicationAdapter(
            runner, state / "staging" / "applications"
        ),
        "native_application": NativeApplicationAdapter(runner),
        "docker_sandbox": DockerSandboxAdapter(sbx_runner),
    }
    core = ExecutorCore(
        policy=config.policy,
        store=StateStore(state / "executor.sqlite"),
        signer=signer,
        pending=config.pending,
        confirmation=config.confirmation,
        adapters=adapters,
    )
    uvicorn.run(create_app(core), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
