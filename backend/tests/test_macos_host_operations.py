"""Focused backend contract and trust-boundary tests for macOS host receipts."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from src import macos_host_operations as host


@pytest.fixture
def plan() -> host.HostOperationPlan:
    return host.HostOperationPlan.model_validate(
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
def signing_material(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_path = tmp_path / "receipt-signing.pub"
    public_path.write_bytes(public)
    public_path.chmod(0o444)
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE", str(public_path))
    config = host.load_operator_config()
    assert config is not None
    return private, config


def _signed_body(
    private: Ed25519PrivateKey,
    config: host.HostOperatorConfig,
    plan: host.HostOperationPlan,
    *,
    digest: str | None = None,
    category: str | None = None,
    status: host.LifecycleState = host.LifecycleState.SUCCEEDED,
    verified: bool | None = None,
    finished_at: datetime | None = None,
    message: str = "done",
) -> bytes:
    receipt = {
        "schema_version": 1,
        "request_digest": digest or plan.digest,
        "request_id": "executor-request-id",
        "terminal_status": status.value,
        "started_at": None,
        "finished_at": (finished_at or datetime.now(UTC)).isoformat(),
        "action_category": category or plan.action.category,
        "executable": "/usr/bin/uname",
        "argv_summary": ["/usr/bin/uname", "-m"],
        "working_directory": None,
        "approved_paths": [],
        "observed_paths": [],
        "artifact_hashes": [],
        "process": {
            "pid": None,
            "exit_code": 0,
            "stdout": "must not reach Coding",
            "stderr": "",
            "output_truncated": False,
            "timed_out": False,
            "cancelled": False,
        },
        "verified_outcome": (
            status is host.LifecycleState.SUCCEEDED if verified is None else verified
        ),
        "observed_mutations": [],
        "rollback": {
            "attempted": False,
            "succeeded": None,
            "detail": "not required",
        },
        "remaining_human_step": None,
        "message": message,
    }
    if status.terminal:
        # The executor signs its model's JSON-mode representation (not the incoming
        # timestamp spelling), so use the exact same normalization here.
        receipt = host.Receipt.model_validate_json(json.dumps(receipt)).model_dump(
            mode="json"
        )
    payload = host.canonical_json_bytes(receipt)
    envelope = {
        "receipt": receipt,
        "algorithm": "Ed25519",
        "key_id": config.key_id,
        "signature": base64.b64encode(private.sign(payload)).decode("ascii"),
    }
    return json.dumps(envelope).encode()


class _Client:
    def __init__(self, body: bytes):
        self.body = body
        self.calls: list[str] = []

    def fetch(self, digest: str) -> bytes:
        self.calls.append(digest)
        return self.body


def test_strict_mirrored_schema_rejects_extra_and_coerced_values(plan):
    data = plan.model_dump()
    data["shell_command"] = "sh -c id"
    with pytest.raises(ValidationError):
        host.HostOperationPlan.model_validate(data)
    data.pop("shell_command")
    data["timeout_seconds"] = "10"
    with pytest.raises(ValidationError):
        host.HostOperationPlan.model_validate(data)


def test_digest_matches_executor_golden_vector(plan):
    assert plan.canonical_bytes() == (
        b'{"action":{"application_id":null,"category":"host_inspection",'
        b'"query":"architecture","target_path":null},"expected_mutations":[],'
        b'"expiry_seconds":300,"output_limit_bytes":4096,"privilege":"user",'
        b'"rollback":{"may_require_human_inspection":false,'
        b'"removes_only_request_created_paths":true,"strategy":"none"},'
        b'"timeout_seconds":10}'
    )
    assert plan.digest == "832c6db37962a817139f5593a5d2e3aa5b85e8586f3d9b922a2924722b0f4313"


def test_operator_config_requires_complete_read_only_public_key(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_URL", "http://127.0.0.1:8765")
    assert host.load_operator_config() is None
    key = tmp_path / "key"
    key.write_bytes(b"x" * 32)
    key.chmod(0o644)
    monkeypatch.setenv("MACOS_HOST_EXECUTOR_PUBLIC_KEY_FILE", str(key))
    assert host.load_operator_config() is None
    key.chmod(0o444)
    assert host.load_operator_config() is not None


def test_valid_receipt_is_bounded_and_redacted(plan, signing_material):
    private, config = signing_material
    client = _Client(
        _signed_body(
            private,
            config,
            plan,
            message="token=top-secret completed",
        )
    )
    result = host.fetch_and_verify_receipt(plan, config, client=client)
    assert client.calls == [plan.digest]
    assert "must not reach Coding" not in result
    assert "/usr/bin/uname" not in result
    assert "top-secret" not in result
    assert "[REDACTED]" in result
    assert len(result.encode()) < 8192


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"digest": "b" * 64}, "digest_mismatch"),
        ({"category": "homebrew"}, "category_mismatch"),
        ({"verified": False}, "outcome_mismatch"),
    ],
)
def test_rejects_mismatched_and_invalid_outcome_receipts(
    plan, signing_material, change, error
):
    private, config = signing_material
    body = _signed_body(private, config, plan, **change)
    with pytest.raises(host.HostOperationError, match=error):
        host.fetch_and_verify_receipt(plan, config, client=_Client(body))


def test_rejects_nonterminal_receipt_even_when_signed(plan, signing_material):
    private, config = signing_material
    body = _signed_body(
        private, config, plan, status=host.LifecycleState.RUNNING, verified=False
    )
    with pytest.raises(host.HostOperationError, match="unverifiable"):
        host.fetch_and_verify_receipt(plan, config, client=_Client(body))


def test_rejects_forged_and_wrong_key_id_receipts(plan, signing_material):
    private, config = signing_material
    forged = bytearray(_signed_body(private, config, plan))
    forged[-10] = ord("x")
    with pytest.raises(host.HostOperationError, match="unverifiable"):
        host.fetch_and_verify_receipt(plan, config, client=_Client(bytes(forged)))

    body = json.loads(_signed_body(private, config, plan))
    body["key_id"] = "wrong-key"
    with pytest.raises(host.HostOperationError, match="key_mismatch"):
        host.fetch_and_verify_receipt(
            plan, config, client=_Client(json.dumps(body).encode())
        )


def test_terminal_receipts_remain_durable_after_plan_expiry(plan, signing_material):
    private, config = signing_material
    old_finished_at = datetime.now(UTC) - timedelta(days=30)
    for status in (host.LifecycleState.EXPIRED, host.LifecycleState.FAILED):
        body = _signed_body(
            private,
            config,
            plan,
            status=status,
            finished_at=old_finished_at,
        )
        result = host.fetch_and_verify_receipt(plan, config, client=_Client(body))
        assert f'"terminal_status":"{status.value}"' in result
        assert '"verified_outcome":false' in result


def test_missing_receipt_and_duplicate_retrieval_have_no_execution_path(
    plan, signing_material
):
    private, config = signing_material

    class Missing:
        def fetch(self, _digest: str) -> bytes:
            raise host.HostOperationError("host_receipt_unavailable")

    with pytest.raises(host.HostOperationError, match="unavailable"):
        host.fetch_and_verify_receipt(plan, config, client=Missing())

    client = _Client(_signed_body(private, config, plan))
    first = host.fetch_and_verify_receipt(plan, config, client=client)
    second = host.fetch_and_verify_receipt(plan, config, client=client)
    assert first == second
    assert client.calls == [plan.digest, plan.digest]
    assert not hasattr(host.ReceiptClient, "confirm")
    assert not hasattr(host.ReceiptClient, "execute")
    assert not hasattr(config, "token")
    assert not hasattr(config, "private_key")


def test_tool_accepts_json_arrays_and_only_fetches_existing_receipt(
    monkeypatch, plan, signing_material
):
    _private, config = signing_material
    calls = []

    def receipt_only(received_plan, received_config):
        calls.append((received_plan.digest, received_config.key_id))
        return "verified"

    monkeypatch.setattr(host, "fetch_and_verify_receipt", receipt_only)
    tool = host.create_request_macos_host_operation_tool(config)
    assert tool.invoke(plan.model_dump(mode="json")) == "verified"
    assert calls == [(plan.digest, config.key_id)]


def test_receipt_client_uses_only_fixed_get_route(monkeypatch):
    captured = {}

    class Response:
        headers = {"Content-Length": "2"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b"{}"

    class Opener:
        def open(self, request, timeout):
            captured.update(url=request.full_url, method=request.method, timeout=timeout)
            return Response()

    client = host.ReceiptClient("http://127.0.0.1:8765")
    monkeypatch.setattr(client, "_opener", Opener())
    assert client.fetch("a" * 64) == b"{}"
    assert captured == {
        "url": f"http://127.0.0.1:8765/v1/receipts/{'a' * 64}",
        "method": "GET",
        "timeout": 5.0,
    }
