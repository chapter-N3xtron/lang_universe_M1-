from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from macos_host_executor.models import (
    ConfirmationAttempt,
    HostOperationPlan,
    HostOperationRequest,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def inspection_plan() -> HostOperationPlan:
    return HostOperationPlan.model_validate(
        {
            "action": {"category": "host_inspection", "query": "architecture"},
            "expected_mutations": (),
            "privilege": "user",
            "timeout_seconds": 10,
            "output_limit_bytes": 4096,
            "rollback": {
                "strategy": "none",
                "removes_only_request_created_paths": True,
                "may_require_human_inspection": False,
            },
            "expiry_seconds": 300,
        }
    )


@pytest.fixture
def confirmation_attempt(inspection_plan: HostOperationPlan) -> ConfirmationAttempt:
    return ConfirmationAttempt(
        thread_id="thread-actual", interrupt_id="interrupt:one", plan=inspection_plan
    )


@pytest.fixture
def inspection_request(
    confirmation_attempt: ConfirmationAttempt, now: datetime
) -> HostOperationRequest:
    return HostOperationRequest.from_attempt(confirmation_attempt, now=now)


@pytest.fixture
def roots(tmp_path: Path) -> dict[str, Path]:
    values = {}
    for name in ("inspect", "downloads", "artifacts", "applications", "work", "output"):
        values[name] = tmp_path / name
        values[name].mkdir()
    return values


def hash_file(path: Path, content: bytes = b"approved") -> str:
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()
