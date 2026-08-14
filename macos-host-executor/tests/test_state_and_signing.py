from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from macos_host_executor.errors import StateConflictError
from macos_host_executor.models import (
    ConfirmationAttempt,
    HostOperationRequest,
    LifecycleState,
    Receipt,
)
from macos_host_executor.signing import ReceiptSigner, verify_signed_receipt
from macos_host_executor.state import StateStore


def receipt(digest: str, state: LifecycleState) -> Receipt:
    return Receipt(
        request_digest=digest,
        request_id="request_1234",
        terminal_status=state,
        finished_at=datetime.now(UTC),
        action_category="host_inspection",
        executable="/usr/bin/uname",
        argv_summary=("/usr/bin/uname", "-m"),
    )


def test_single_use_and_monotonic_state(tmp_path: Path, inspection_request) -> None:
    store = StateStore(tmp_path / "state" / "executor.sqlite")
    assert store.create(inspection_request)[0] == LifecycleState.REQUESTED
    assert store.create(inspection_request)[0] == LifecycleState.REQUESTED
    store.claim_confirmation(inspection_request.digest)
    with pytest.raises(StateConflictError):
        store.claim_confirmation(inspection_request.digest)
    with pytest.raises(StateConflictError):
        store.transition(inspection_request.digest, LifecycleState.RUNNING)


def test_plan_digest_cannot_be_rebound_to_another_interrupt(
    tmp_path: Path, inspection_request
) -> None:
    store = StateStore(tmp_path / "binding.sqlite")
    store.create(inspection_request)
    rebound = HostOperationRequest.from_attempt(
        ConfirmationAttempt(
            thread_id="another-thread",
            interrupt_id="another-interrupt",
            plan=inspection_request.plan,
        )
    )
    with pytest.raises(StateConflictError, match="another interrupt"):
        store.create(rebound)


def test_restart_marks_running_uncertain_without_replay(
    tmp_path: Path, inspection_request
) -> None:
    store = StateStore(tmp_path / "executor.sqlite")
    store.create(inspection_request)
    store.transition(inspection_request.digest, LifecycleState.CONFIRMING)
    store.transition(inspection_request.digest, LifecycleState.CONFIRMED)
    store.transition(inspection_request.digest, LifecycleState.RUNNING)
    assert store.recover_after_restart() == 1
    assert store.get(inspection_request.digest)[0] == LifecycleState.UNCERTAIN


def test_ed25519_signed_receipt_detects_tampering() -> None:
    key = Ed25519PrivateKey.generate()
    signer = ReceiptSigner(key)
    signed = signer.sign(receipt("a" * 64, LifecycleState.SUCCEEDED))
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    assert signer.public_key_bytes() == public
    verify_signed_receipt(signed, public)
    tampered = signed.model_copy(
        update={"receipt": signed.receipt.model_copy(update={"message": "changed"})}
    )
    with pytest.raises(InvalidSignature):
        verify_signed_receipt(tampered, public)


def test_public_key_export_contains_no_private_material(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    signer = ReceiptSigner(key)
    destination = tmp_path / "public" / "receipt-signing.pub"
    assert signer.export_public_key(destination) == destination
    assert destination.read_bytes() == signer.public_key_bytes()
    assert len(destination.read_bytes()) == 32
    assert destination.stat().st_mode & 0o777 == 0o644
