from __future__ import annotations

import asyncio
import time

import pytest
from docker_broker.audit import AuditLog
from docker_broker.errors import ApprovalRejected, ConflictError, LeaseError
from docker_broker.leases import LeaseStore


class Confirmation:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.calls = 0

    async def approve(self, **_values) -> None:
        self.calls += 1
        if not self.approved:
            raise ApprovalRejected("rejected")


@pytest.mark.asyncio
async def test_lease_requires_approval_and_revokes(repository, tmp_path):
    confirmation = Confirmation()
    store = LeaseStore(confirmation, AuditLog(tmp_path / "audit.jsonl"))
    token, lease = await store.activate(
        session_id="thread-one",
        owner_id="owner-one",
        workspace=repository,
        lease_seconds=300,
    )
    assert confirmation.calls == 1
    assert (await store.authorize(token)).scope_digest == lease.scope_digest
    with pytest.raises(ConflictError):
        await store.activate(
            session_id="thread-one",
            owner_id="owner-one",
            workspace=repository,
            lease_seconds=300,
        )
    assert await store.revoke(token)
    assert lease.revoked.is_set()
    with pytest.raises(LeaseError):
        await store.authorize(token)
    assert token not in (tmp_path / "audit.jsonl").read_text()


@pytest.mark.asyncio
async def test_rejected_confirmation_creates_no_authority(repository, tmp_path):
    store = LeaseStore(Confirmation(False), AuditLog(tmp_path / "audit.jsonl"))
    with pytest.raises(ApprovalRejected):
        await store.activate(
            session_id="thread-one",
            owner_id="owner-one",
            workspace=repository,
            lease_seconds=300,
        )


@pytest.mark.asyncio
async def test_expired_lease_fails_closed(repository, tmp_path):
    store = LeaseStore(Confirmation(), AuditLog(tmp_path / "audit.jsonl"))
    token, lease = await store.activate(
        session_id="thread-one",
        owner_id="owner-one",
        workspace=repository,
        lease_seconds=300,
    )
    object.__setattr__(lease, "expires_monotonic", time.monotonic() - 1)
    with pytest.raises(LeaseError):
        await store.authorize(token)
    assert lease.revoked.is_set()


class BlockingConfirmation:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def approve(self, **_values) -> None:
        self.entered.set()
        await self.release.wait()


@pytest.mark.asyncio
async def test_confirmation_does_not_hold_lease_lock(repository, tmp_path):
    confirmation = BlockingConfirmation()
    store = LeaseStore(confirmation, AuditLog(tmp_path / "audit.jsonl"))
    activation = asyncio.create_task(
        store.activate(
            session_id="thread-one",
            owner_id="owner-one",
            workspace=repository,
            lease_seconds=300,
        )
    )
    await confirmation.entered.wait()
    assert not await asyncio.wait_for(store.revoke("not-a-real-token"), timeout=0.2)
    with pytest.raises(ConflictError):
        await asyncio.wait_for(
            store.activate(
                session_id="thread-one",
                owner_id="owner-one",
                workspace=repository,
                lease_seconds=300,
            ),
            timeout=0.2,
        )
    confirmation.release.set()
    token, _ = await activation
    assert await store.revoke(token)
