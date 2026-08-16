from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from docker_broker.errors import ApprovalRejected


class NativeConfirmation:
    def __init__(self, osascript_path: Path, *, allow_builds: bool = False) -> None:
        self._osascript_path = osascript_path
        self._allow_builds = allow_builds
        self._lock = asyncio.Lock()

    async def approve(
        self,
        *,
        session_id: str,
        owner_id: str,
        workspace: Path,
        lease_seconds: int,
    ) -> None:
        allowed_operations = (
            "pull, build, up, start, stop, restart, and down"
            if self._allow_builds
            else "pull, up, start, stop, restart, and down (builds are blocked)"
        )
        message = (
            "Allow Docker management for one Coder conversation?\n\n"
            f"Session: {session_id}\n"
            f"Owner: {owner_id}\n"
            f"Repository: {workspace}\n"
            f"Safety limit: {lease_seconds // 60} minutes\n\n"
            f"Allowed: validated Compose {allowed_operations}.\n"
            "Blocked: privileged containers, host escape mounts, external resources, "
            "non-loopback ports, Docker sockets, devices, and volume deletion.\n\n"
            "Running containers can continue after this authority is revoked."
        )
        script = (
            "on run argv\n"
            'display dialog (item 1 of argv) with title "Jasper Docker Broker" '
            'buttons {"Deny", "Allow"} default button "Deny" '
            'cancel button "Deny" giving up after 120\n'
            "end run"
        )
        async with self._lock:
            process = await asyncio.create_subprocess_exec(
                str(self._osascript_path),
                "-e",
                script,
                message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                output, _ = await asyncio.wait_for(process.communicate(), timeout=125)
            except BaseException:
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.wait()
                raise
        if process.returncode != 0 or b"button returned:Allow" not in output:
            raise ApprovalRejected("Docker session approval was not granted")
