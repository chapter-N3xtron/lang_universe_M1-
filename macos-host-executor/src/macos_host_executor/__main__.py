"""Production CLI for the explicitly configured, loopback-only executor."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .adapters import (
    ApplicationAdapter,
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
    policy_config = config.policy.config
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
