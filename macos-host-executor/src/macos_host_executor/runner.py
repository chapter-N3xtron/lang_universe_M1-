"""Shell-free subprocess runner with process-group ownership and bounded capture."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunResult:
    exit_code: int | None
    stdout: str
    stderr: str
    output_truncated: bool
    timed_out: bool
    cancelled: bool
    pid: int | None


class _Capture:
    def __init__(self, limit: int):
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.lock = threading.Lock()

    def drain(self, stream: object) -> None:
        read = stream.read
        while chunk := read(8192):
            with self.lock:
                remaining = max(0, self.limit - len(self.data))
                self.data.extend(chunk[:remaining])
                self.truncated |= len(chunk) > remaining

    def text(self) -> str:
        return bytes(self.data).decode("utf-8", errors="replace")


class SubprocessRunner:
    """Executes an already policy-built argv; callers cannot provide environment."""

    def __init__(
        self,
        staging_directory: Path,
        trusted_environment: Mapping[str, str] | None = None,
    ):
        self.staging_directory = staging_directory
        self.staging_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.staging_directory, 0o700)
        runtime_home = self.staging_directory.parent / "runtime-home"
        runtime_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(runtime_home, 0o700)
        base = {
            "HOME": str(runtime_home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": str(self.staging_directory),
        }
        if trusted_environment:
            base.update(trusted_environment)
        self._environment = base

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout_seconds: int,
        output_limit_bytes: int,
        cancel: threading.Event,
    ) -> RunResult:
        if not argv or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
            raise ValueError("argv must contain non-empty NUL-free strings")
        stdout = _Capture(output_limit_bytes // 2)
        stderr = _Capture(output_limit_bytes - output_limit_bytes // 2)
        with tempfile.TemporaryDirectory(dir=self.staging_directory) as temp:
            environment = dict(self._environment)
            environment["TMPDIR"] = temp
            process = subprocess.Popen(
                list(argv),
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                close_fds=True,
            )
            threads = [
                threading.Thread(
                    target=stdout.drain, args=(process.stdout,), daemon=True
                ),
                threading.Thread(
                    target=stderr.drain, args=(process.stderr,), daemon=True
                ),
            ]
            for thread in threads:
                thread.start()
            deadline = time.monotonic() + timeout_seconds
            timed_out = False
            cancelled = False
            while process.poll() is None:
                if cancel.is_set():
                    cancelled = True
                    self._terminate_group(process)
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    self._terminate_group(process)
                    break
                time.sleep(0.02)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._kill_group(process)
                process.wait(timeout=2)
            for thread in threads:
                thread.join(timeout=1)
            return RunResult(
                exit_code=process.returncode,
                stdout=stdout.text(),
                stderr=stderr.text(),
                output_truncated=stdout.truncated or stderr.truncated,
                timed_out=timed_out,
                cancelled=cancelled,
                pid=process.pid,
            )

    @staticmethod
    def _terminate_group(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    @staticmethod
    def _kill_group(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
