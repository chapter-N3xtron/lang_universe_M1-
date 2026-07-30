"""Bounded ACP initialization probe for Deep Agents Code.

The probe starts ``dcode --acp``, performs only the protocol initialization
handshake, and reports aggregate compatibility evidence. It never sends a
coding prompt or prints child-process logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any


async def run_probe(
    executable: Path, workspace: Path, model_name: str, timeout: int
) -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        str(executable),
        "--acp",
        "--model",
        f"ollama:{model_name}",
        "--no-mcp",
        "--allow-fs-tools",
        "read_file",
        cwd=workspace,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": 1,
            "clientCapabilities": {
                "fs": {"readTextFile": False, "writeTextFile": False},
                "terminal": False,
                "auth": {"terminal": False},
            },
        },
    }

    try:
        process.stdin.write((json.dumps(request) + "\n").encode())
        await process.stdin.drain()
        line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
        response = json.loads(line)
        result = response.get("result", {})
        protocol_version = result.get("protocolVersion")
        return {
            "path": "dcode-acp",
            "model": model_name,
            "request_id_matched": response.get("id") == 1,
            "protocol_version": protocol_version,
            "json_rpc_error": "error" in response,
            "success": (
                response.get("id") == 1
                and protocol_version == 1
                and "error" not in response
            ),
        }
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:27b")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    executable = args.executable.expanduser().resolve()
    workspace = args.workspace.resolve()
    if not executable.is_file():
        raise SystemExit("dcode executable not found")
    if not (workspace / "README.md").is_file():
        raise SystemExit("workspace must contain README.md")

    result = asyncio.run(
        run_probe(executable, workspace, args.model, args.timeout)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
