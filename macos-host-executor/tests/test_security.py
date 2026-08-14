from __future__ import annotations

from pathlib import Path

import pytest
from conftest import hash_file

from macos_host_executor.errors import InputChangedError, PolicyDeniedError
from macos_host_executor.security import (
    canonical_destination_absent,
    canonical_existing,
    redact,
    reject_command_like_text,
    verify_hash,
)


def test_authorized_root_and_symlink_escape(
    roots: dict[str, Path], tmp_path: Path
) -> None:
    approved = roots["work"] / "scene.blend"
    approved.write_bytes(b"blend")
    assert canonical_existing(str(approved), (str(roots["work"]),)) == approved
    outside = tmp_path / "outside"
    outside.write_bytes(b"secret")
    link = roots["work"] / "link"
    link.symlink_to(outside)
    with pytest.raises(PolicyDeniedError, match="symlink"):
        canonical_existing(str(link), (str(roots["work"]),))
    with pytest.raises(PolicyDeniedError, match="outside"):
        canonical_existing(str(outside), (str(roots["work"]),))


def test_destination_must_be_absent(roots: dict[str, Path]) -> None:
    destination = roots["downloads"] / "blender.dmg"
    assert (
        canonical_destination_absent(str(destination), (str(roots["downloads"]),))
        == destination
    )
    destination.touch()
    with pytest.raises(PolicyDeniedError, match="absent"):
        canonical_destination_absent(str(destination), (str(roots["downloads"]),))


def test_hash_revalidation_detects_change(tmp_path: Path) -> None:
    path = tmp_path / "script.py"
    expected = hash_file(path)
    verify_hash(path, expected)
    path.write_bytes(b"changed")
    with pytest.raises(InputChangedError):
        verify_hash(path, expected)


def test_explicit_denials_and_redaction() -> None:
    for value in (
        "bash -c id",
        "git push origin main",
        "docker ps",
        "token=$(security find-generic-password)",
    ):
        with pytest.raises(PolicyDeniedError):
            reject_command_like_text((value,))
    text = redact("token=abc password: xyz\x00")
    assert "abc" not in text and "xyz" not in text and "\x00" not in text
