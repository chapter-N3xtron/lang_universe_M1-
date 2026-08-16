from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class AuditLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def write(self, event: str, **values: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **values,
        }
        line = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
        flags = (
            os.O_APPEND
            | os.O_CREAT
            | os.O_WRONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        with self._lock:
            if self._path.exists():
                existing = self._path.lstat()
                if not stat.S_ISREG(existing.st_mode):
                    raise RuntimeError("audit log path is unsafe")
                if existing.st_size >= 10_000_000:
                    os.replace(self._path, self._path.with_suffix(".jsonl.1"))
            descriptor = os.open(self._path, flags, 0o600)
            try:
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.geteuid()
                    or metadata.st_mode & 0o077
                ):
                    raise RuntimeError("audit log ownership or permissions are unsafe")
                view = memoryview(line.encode())
                while view:
                    view = view[os.write(descriptor, view) :]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
