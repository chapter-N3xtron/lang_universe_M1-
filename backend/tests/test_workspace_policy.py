"""Focused tests for host-path policy and truthful Custodian identity."""

from __future__ import annotations

import os

import pytest

from src import workspace_policy
from src.workspace_policy import (
    WorkspacePolicyError,
    canonical_workspace,
    execution_manifest,
    format_execution_manifest,
    host_worker_available,
)


def test_host_workspace_is_lexical_and_need_not_exist_in_agent_container(
    monkeypatch, tmp_path
):
    authorized = tmp_path / "authorized"
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(authorized))
    selected = authorized / "host-only-repository"

    first = canonical_workspace(str(selected))
    resumed = canonical_workspace(str(first))

    assert first == selected
    assert resumed == selected
    assert not selected.exists()


def test_missing_selection_unauthorized_and_noncanonical_fail_without_fallback(
    monkeypatch, tmp_path
):
    authorized = tmp_path / "authorized"
    outside = tmp_path / "sibling-repository"
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(authorized))

    for candidate in (None, "", str(outside), f"{authorized}/child/../other"):
        with pytest.raises(WorkspacePolicyError):
            canonical_workspace(candidate)


def test_manifest_truthfully_identifies_native_custodian(monkeypatch, tmp_path):
    selected = tmp_path / "host-only"
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    monkeypatch.setenv("CUSTODIAN_WORKER_URL", "")

    manifest = execution_manifest(selected)

    assert manifest == {
        "filesystem_origin": "native_custodian",
        "selected_repository": str(selected),
        "command_runtime": "native_custodian_host",
        "host_worker": "unavailable",
    }
    rendered = format_execution_manifest(manifest)
    assert str(selected) in rendered
    assert "bind_mount" not in rendered
    assert "linux_agent_server_container" not in rendered


def test_worker_availability_requires_a_healthy_response(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"ok":true,"service":"custodian-worker"}'

    monkeypatch.setenv("CUSTODIAN_WORKER_URL", "http://worker.test")
    monkeypatch.setattr(
        workspace_policy.urllib.request, "urlopen", lambda *_args, **_kwargs: Response()
    )

    assert host_worker_available() is True


def test_relative_authorized_root_is_ignored_fail_closed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", os.curdir)

    with pytest.raises(WorkspacePolicyError, match="outside authorized roots"):
        canonical_workspace(tmp_path)
