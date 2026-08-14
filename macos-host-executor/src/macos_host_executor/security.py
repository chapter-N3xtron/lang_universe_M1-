"""Canonical path, hash, redaction, and explicit capability denials."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Iterable
from pathlib import Path

from .errors import InputChangedError, PolicyDeniedError

_DENIED_WORDS = frozenset(
    {
        "bash",
        "curl",
        "docker",
        "env",
        "gh",
        "git",
        "launchctl",
        "osascript",
        "security",
        "sh",
        "ssh",
        "sudo",
        "zsh",
    }
)
_SHELL_METACHARACTERS = re.compile(r"[;&|`$><\n\r]")
_SECRET = re.compile(
    r"(?i)(authorization|bearer|password|passwd|secret|token|private[_ -]?key)"
    r"\s*[:=]\s*([^\s,;]+)"
)


def reject_command_like_text(values: Iterable[str]) -> None:
    """Defense in depth; typed policies should never treat these as commands."""
    for value in values:
        if _SHELL_METACHARACTERS.search(value):
            raise PolicyDeniedError("shell metacharacters are denied")
        words = {part.lower() for part in re.split(r"[^A-Za-z0-9_+-]+", value)}
        if words & _DENIED_WORDS:
            raise PolicyDeniedError("prohibited host capability named in request")


def _within(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def canonical_existing(
    path: str, roots: Iterable[str], *, regular_file: bool = False
) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise PolicyDeniedError("path must be absolute")
    _reject_symlink_components(candidate)
    try:
        canonical = candidate.resolve(strict=True)
    except OSError as exc:
        raise PolicyDeniedError("path does not exist") from exc
    canonical_roots = tuple(Path(root).resolve(strict=True) for root in roots)
    if not _within(canonical, canonical_roots):
        raise PolicyDeniedError("path is outside authorized roots")
    if regular_file and not canonical.is_file():
        raise PolicyDeniedError("path must be a regular file")
    return canonical


def canonical_destination_absent(path: str, roots: Iterable[str]) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.name in {"", ".", ".."}:
        raise PolicyDeniedError("destination must be an absolute named path")
    if candidate.exists() or candidate.is_symlink():
        raise PolicyDeniedError("destination must be absent")
    _reject_symlink_components(candidate.parent)
    try:
        parent = candidate.parent.resolve(strict=True)
    except OSError as exc:
        raise PolicyDeniedError("destination parent does not exist") from exc
    canonical_roots = tuple(Path(root).resolve(strict=True) for root in roots)
    if not _within(parent, canonical_roots):
        raise PolicyDeniedError("destination is outside authorized roots")
    return parent / candidate.name


def canonical_configured_executable(path: str, allowed: Iterable[str]) -> Path:
    if path not in set(allowed):
        raise PolicyDeniedError("executable is not exactly allowlisted")
    executable = Path(path)
    _reject_symlink_components(executable)
    try:
        info = executable.stat()
    except OSError as exc:
        raise PolicyDeniedError("configured executable is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or not os.access(executable, os.X_OK):
        raise PolicyDeniedError(
            "configured executable is not an executable regular file"
        )
    return executable.resolve(strict=True)


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            if current.is_symlink():
                raise PolicyDeniedError("symlink path components are denied")
        except OSError as exc:
            raise PolicyDeniedError("path could not be inspected") from exc


def sha256_file(path: Path, *, max_bytes: int = 2_147_483_648) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise PolicyDeniedError("input exceeds hashing limit")
                digest.update(chunk)
    except OSError as exc:
        raise PolicyDeniedError("input could not be hashed") from exc
    return digest.hexdigest()


def verify_hash(path: Path, expected: str) -> None:
    if sha256_file(path) != expected:
        raise InputChangedError("approval-bound input hash changed")


def redact(text: str, *, home: str | None = None, limit: int = 65_536) -> str:
    bounded = text[:limit]
    bounded = _SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", bounded)
    if home:
        bounded = bounded.replace(home, "~")
    return "".join(
        char if char.isprintable() or char in "\n\t" else "?" for char in bounded
    )
