from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from docker_broker.api import create_app
from docker_broker.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="docker-broker")
    parser.add_argument("--allowed-root", action="append", required=True)
    parser.add_argument(
        "--state-directory",
        default=str(Path.home() / ".jasper" / "docker-broker"),
    )
    parser.add_argument("--docker-path", default="/usr/local/bin/docker")
    parser.add_argument("--agent-server-url", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--lease-seconds", type=int, default=14400)
    parser.add_argument("--allow-builds", action="store_true")
    parser.add_argument("--host", choices=["127.0.0.1", "::1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    arguments = parser.parse_args()
    if not 1024 <= arguments.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if not 300 <= arguments.lease_seconds <= 43200:
        parser.error("lease-seconds must be between 300 and 43200")
    settings = Settings.from_values(
        allowed_roots=arguments.allowed_root,
        state_directory=arguments.state_directory,
        docker_path=arguments.docker_path,
        agent_server_url=arguments.agent_server_url,
        owner_id=arguments.owner_id,
        lease_seconds=arguments.lease_seconds,
        allow_builds=arguments.allow_builds,
    )
    uvicorn.run(
        create_app(settings),
        host=arguments.host,
        port=arguments.port,
        access_log=False,
        server_header=False,
        limit_concurrency=32,
        backlog=32,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=10,
    )
