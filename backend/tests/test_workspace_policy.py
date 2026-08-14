"""Focused tests for exact workspace and truthful execution identity."""

from __future__ import annotations

import os

import pytest

from src.workspace_policy import (
    WorkspacePolicyError,
    canonical_workspace,
    execution_manifest,
    format_execution_manifest,
)


def test_existing_empty_workspace_is_canonical_and_stable(monkeypatch, tmp_path):
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    selected = authorized / "empty-repository"
    selected.mkdir()
    alias = authorized / "selected-alias"
    alias.symlink_to(selected, target_is_directory=True)
    sibling = authorized / "other-repository"
    sibling.mkdir()
    (sibling / ".git").mkdir()
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(authorized))

    first_selection = canonical_workspace(str(alias))
    refreshed = canonical_workspace(str(first_selection))
    reopened = canonical_workspace(str(refreshed))
    resumed = canonical_workspace(str(reopened))

    assert first_selection == selected.resolve()
    assert refreshed == reopened == resumed == selected.resolve()
    assert list(selected.iterdir()) == []
    assert resumed != sibling.resolve()


def test_missing_or_unauthorized_workspace_fails_without_fallback(
    monkeypatch, tmp_path
):
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    outside = tmp_path / "sibling-repository"
    outside.mkdir()
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(authorized))

    for candidate in (None, "", str(authorized / "missing"), str(outside)):
        with pytest.raises(WorkspacePolicyError):
            canonical_workspace(candidate)

    assert canonical_workspace.__module__ == "src.workspace_policy"


def test_manifest_distinguishes_filesystem_runtime_and_host_capability(
    monkeypatch, tmp_path
):
    selected = tmp_path / "empty"
    selected.mkdir()
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", str(tmp_path))
    manifest = execution_manifest(selected)

    assert manifest == {
        "filesystem_origin": "macos_host_bind_mount",
        "selected_repository": str(selected.resolve()),
        "command_runtime": "linux_agent_server_container",
        "native_host_operations": "unavailable_without_separate_approval",
        "host_operation_request": "unavailable",
    }
    rendered = format_execution_manifest(manifest)
    assert str(selected.resolve()) in rendered
    assert "/workspace" not in rendered


def test_relative_authorized_root_is_ignored_fail_closed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKSPACE_AUTHORIZED_ROOTS", os.curdir)

    with pytest.raises(WorkspacePolicyError, match="outside authorized roots"):
        canonical_workspace(tmp_path)
