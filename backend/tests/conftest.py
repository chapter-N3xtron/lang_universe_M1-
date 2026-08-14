"""Backend test configuration for explicit workspace authorization."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _authorize_pytest_workspaces(monkeypatch, tmp_path_factory):
    """Authorize only pytest's temporary root unless a test overrides policy."""

    test_root = tmp_path_factory.getbasetemp().resolve().parent
    roots = [test_root]
    system_tmp = Path("/tmp").resolve()
    if system_tmp not in roots:
        roots.append(system_tmp)
    monkeypatch.setenv(
        "WORKSPACE_AUTHORIZED_ROOTS", os.pathsep.join(str(root) for root in roots)
    )
