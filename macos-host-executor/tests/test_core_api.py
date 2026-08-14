from __future__ import annotations

import threading
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from macos_host_executor.adapters import AdapterResult
from macos_host_executor.api import create_app, require_loopback_bind
from macos_host_executor.core import ExecutorCore
from macos_host_executor.errors import StateConflictError
from macos_host_executor.models import LifecycleState, RollbackReport
from macos_host_executor.policy import ActionPolicy, PolicyConfig
from macos_host_executor.signing import ReceiptSigner
from macos_host_executor.state import StateStore


class FakePending:
    value = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def is_pending(self, thread_id: str, interrupt_id: str, plan_digest: str) -> bool:
        self.calls.append((thread_id, interrupt_id, plan_digest))
        return self.value


class FakeConfirmation:
    value = True

    def confirm(self, request, plan) -> bool:
        return self.value


class FakeAdapter:
    def __init__(self, result: AdapterResult | None = None):
        self.calls = 0
        self.result = result or AdapterResult(True, True, message="architecture=arm64")

    def execute(
        self, action, plan, *, timeout: int, output_limit: int, cancel: threading.Event
    ) -> AdapterResult:
        self.calls += 1
        return self.result


def make_core(
    tmp_path: Path, adapter: FakeAdapter, pending=None, confirmation=None
) -> ExecutorCore:
    return ExecutorCore(
        policy=ActionPolicy(PolicyConfig()),
        store=StateStore(tmp_path / "state.sqlite"),
        signer=ReceiptSigner(Ed25519PrivateKey.generate()),
        pending=pending or FakePending(),
        confirmation=confirmation or FakeConfirmation(),
        adapters={"host_inspection": adapter},
    )


def wait(core: ExecutorCore, digest: str):
    for _ in range(200):
        value = core.status(digest)
        if value and value[0].terminal:
            return value
        time.sleep(0.01)
    raise AssertionError("executor did not finish")


def test_fake_adapter_executes_once_and_returns_signed_receipt(
    tmp_path: Path, confirmation_attempt
) -> None:
    adapter = FakeAdapter()
    core = make_core(tmp_path, adapter)
    digest = confirmation_attempt.plan.digest
    core.start(confirmation_attempt)
    state, signed = wait(core, digest)
    assert state == LifecycleState.SUCCEEDED
    assert signed.receipt.verified_outcome
    assert signed.receipt.request_digest == digest
    assert adapter.calls == 1
    state2, same = core.start(confirmation_attempt)
    assert state2 == LifecycleState.SUCCEEDED
    assert same == signed
    assert adapter.calls == 1


def test_rejection_and_pending_check_have_no_adapter_effect(
    tmp_path: Path, confirmation_attempt
) -> None:
    adapter = FakeAdapter()
    confirmation = FakeConfirmation()
    confirmation.value = False
    core = make_core(tmp_path, adapter, confirmation=confirmation)
    core.start(confirmation_attempt)
    state, receipt = wait(core, confirmation_attempt.plan.digest)
    assert state == LifecycleState.REJECTED and receipt is not None
    assert adapter.calls == 0


def test_fake_partial_failure_preserves_rollback_accounting(
    tmp_path: Path, confirmation_attempt
) -> None:
    result = AdapterResult(
        success=False,
        verified=False,
        partial=True,
        rollback=RollbackReport(
            attempted=True,
            succeeded=False,
            detail="fake rollback uncertainty",
        ),
        message="fake partial mutation",
    )
    core = make_core(tmp_path, FakeAdapter(result))
    core.start(confirmation_attempt)
    state, signed = wait(core, confirmation_attempt.plan.digest)
    assert state == LifecycleState.PARTIAL
    assert signed.receipt.rollback.succeeded is False
    assert not signed.receipt.verified_outcome


def test_core_restart_creates_signed_uncertain_receipt(
    tmp_path: Path, inspection_request
) -> None:
    store = StateStore(tmp_path / "restart.sqlite")
    store.create(inspection_request)
    store.transition(inspection_request.digest, LifecycleState.CONFIRMING)
    store.transition(inspection_request.digest, LifecycleState.CONFIRMED)
    store.transition(inspection_request.digest, LifecycleState.RUNNING)
    core = ExecutorCore(
        policy=ActionPolicy(PolicyConfig()),
        store=store,
        signer=ReceiptSigner(Ed25519PrivateKey.generate()),
        pending=FakePending(),
        confirmation=FakeConfirmation(),
        adapters={"host_inspection": FakeAdapter()},
    )
    state, signed = core.status(inspection_request.digest)
    assert state == LifecycleState.UNCERTAIN
    assert signed is not None
    assert signed.receipt.remaining_human_step


def test_pending_check_uses_actual_thread_interrupt_and_plan_digest(
    tmp_path: Path, confirmation_attempt
) -> None:
    pending = FakePending()
    pending.value = False
    adapter = FakeAdapter()
    core = make_core(tmp_path, adapter, pending=pending)
    try:
        core.start(confirmation_attempt)
    except StateConflictError:
        pass
    else:
        raise AssertionError("missing pending interrupt was accepted")
    assert pending.calls == [
        (
            confirmation_attempt.thread_id,
            confirmation_attempt.interrupt_id,
            confirmation_attempt.plan.digest,
        )
    ]
    assert adapter.calls == 0


def test_loopback_api_accepts_only_confirmation_attempt(
    tmp_path: Path, confirmation_attempt
) -> None:
    adapter = FakeAdapter()
    core = make_core(tmp_path, adapter)
    app = create_app(core)
    routes = {route.path for route in app.routes}
    assert "/v1/commands" not in routes and "/v1/shell" not in routes
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        assert client.get("/health").status_code == 200
        body = confirmation_attempt.model_dump(mode="json")
        response = client.post("/v1/confirmations", json=body)
        assert response.status_code == 202
        digest = confirmation_attempt.plan.digest
        assert response.json()["plan_digest"] == digest
        wait(core, digest)
        assert client.get(f"/v1/receipts/{digest}").status_code == 200
        body["request_id"] = "client-forged"
        assert client.post("/v1/confirmations", json=body).status_code == 409
        assert client.post("/v1/commands", json={"shell": "id"}).status_code == 404


def test_browser_cors_is_exact_and_credential_free(tmp_path: Path) -> None:
    app = create_app(make_core(tmp_path, FakeAdapter()))
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        allowed = client.options(
            "/v1/confirmations",
            headers={
                "Origin": "http://localhost:3002",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3002"
        assert "access-control-allow-credentials" not in allowed.headers

        denied = client.options(
            "/v1/confirmations",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


def test_non_loopback_bind_is_rejected() -> None:
    require_loopback_bind("127.0.0.1")
    try:
        require_loopback_bind("0.0.0.0")
    except ValueError:
        pass
    else:
        raise AssertionError("non-loopback bind accepted")
