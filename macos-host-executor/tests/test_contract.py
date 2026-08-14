from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from macos_host_executor.models import (
    ConfirmationAttempt,
    HostAction,
    HostOperationPlan,
    HostOperationRequest,
    LifecycleState,
)


def test_plan_digest_is_stable_and_excludes_server_envelope(
    inspection_plan: HostOperationPlan, confirmation_attempt: ConfirmationAttempt, now
) -> None:
    reordered = HostOperationPlan.model_validate_json(inspection_plan.model_dump_json())
    assert reordered.canonical_bytes() == inspection_plan.canonical_bytes()
    assert reordered.digest == inspection_plan.digest
    first = HostOperationRequest.from_attempt(confirmation_attempt, now=now)
    second = HostOperationRequest.from_attempt(
        confirmation_attempt, now=now + timedelta(seconds=1)
    )
    assert first.request_id != second.request_id
    assert first.created_at != second.created_at
    assert first.digest == second.digest == inspection_plan.digest


def test_discriminated_actions_are_strict() -> None:
    adapter = TypeAdapter(HostAction)
    action = adapter.validate_python(
        {
            "category": "homebrew",
            "operation": "install",
            "package_kind": "cask",
            "package": "blender",
        }
    )
    assert action.category == "homebrew"
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "category": "homebrew",
                "operation": "install",
                "package_kind": "cask",
                "package": "blender",
                "argv": ["sh", "-c", "id"],
            }
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "category": "native_application",
                "application_id": "blender",
                "operation": "blender_background_render",
                "working_directory": "/tmp",
            }
        )


def test_client_contract_has_no_server_or_arbitrary_execution_fields() -> None:
    schema = ConfirmationAttempt.model_json_schema()
    serialized = str(schema)
    for denied in (
        "shell_command",
        "environment",
        '"argv"',
        "request_id",
        "created_at",
        "expires_at",
    ):
        assert denied not in serialized


def test_attempt_rejects_server_fields_and_expiry_is_bounded(
    confirmation_attempt: ConfirmationAttempt,
) -> None:
    data = confirmation_attempt.model_dump()
    data["request_id"] = "client-controlled"
    with pytest.raises(ValidationError):
        ConfirmationAttempt.model_validate(data)
    plan = confirmation_attempt.plan.model_dump()
    plan["expiry_seconds"] = 3601
    with pytest.raises(ValidationError):
        HostOperationPlan.model_validate(plan)

    plan = confirmation_attempt.plan.model_dump()
    plan["expected_mutations"] = tuple(
        {
            "operation": "inspect",
            "path": f"/tmp/item-{index}",
            "detail": "bounded review field",
        }
        for index in range(33)
    )
    with pytest.raises(ValidationError):
        HostOperationPlan.model_validate(plan)


def test_server_request_expiration(inspection_request: HostOperationRequest) -> None:
    with pytest.raises(ValueError, match="expired"):
        inspection_request.assert_unexpired(inspection_request.expires_at)


def test_lifecycle_terminal_set() -> None:
    assert LifecycleState.SUCCEEDED.terminal
    assert LifecycleState.UNCERTAIN.terminal
    assert not LifecycleState.RUNNING.terminal
