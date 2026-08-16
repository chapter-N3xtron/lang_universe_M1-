from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from docker_broker.audit import AuditLog
from docker_broker.confirmation import NativeConfirmation
from docker_broker.errors import ConflictError, LeaseError


@dataclass(frozen=True)
class Lease:
    token_digest: str
    session_id: str
    owner_id: str
    workspace: Path
    scope_digest: str
    expires_monotonic: float
    expires_at: datetime
    revoked: asyncio.Event


class LeaseStore:
    def __init__(self, confirmation: NativeConfirmation, audit: AuditLog) -> None:
        self.boot_id = uuid.uuid4().hex
        self._confirmation = confirmation
        self._audit = audit
        self._leases: dict[str, Lease] = {}
        self._scopes: dict[str, str] = {}
        self._pending_scopes: set[str] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _scope_digest(session_id: str, owner_id: str, workspace: Path) -> str:
        material = f"{session_id}\0{owner_id}\0{workspace}".encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _remove_expired(self) -> None:
        now = time.monotonic()
        expired = [
            key for key, lease in self._leases.items() if lease.expires_monotonic <= now
        ]
        for key in expired:
            lease = self._leases.pop(key)
            lease.revoked.set()
            self._scopes.pop(lease.scope_digest, None)
            self._audit.write(
                "lease_expired",
                session_id=lease.session_id,
                owner_id=lease.owner_id,
                workspace=str(lease.workspace),
                scope_digest=lease.scope_digest,
            )

    async def activate(
        self,
        *,
        session_id: str,
        owner_id: str,
        workspace: Path,
        lease_seconds: int,
    ) -> tuple[str, Lease]:
        scope_digest = self._scope_digest(session_id, owner_id, workspace)
        async with self._lock:
            self._remove_expired()
            if scope_digest in self._scopes or scope_digest in self._pending_scopes:
                raise ConflictError("This Docker session is already active")
            self._pending_scopes.add(scope_digest)
        try:
            await self._confirmation.approve(
                session_id=session_id,
                owner_id=owner_id,
                workspace=workspace,
                lease_seconds=lease_seconds,
            )
        except BaseException:
            async with self._lock:
                self._pending_scopes.discard(scope_digest)
            raise
        token = secrets.token_urlsafe(48)
        token_digest = self._token_digest(token)
        expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        lease = Lease(
            token_digest=token_digest,
            session_id=session_id,
            owner_id=owner_id,
            workspace=workspace,
            scope_digest=scope_digest,
            expires_monotonic=time.monotonic() + lease_seconds,
            expires_at=expires_at,
            revoked=asyncio.Event(),
        )
        try:
            await asyncio.to_thread(
                self._audit.write,
                "lease_activated",
                session_id=session_id,
                owner_id=owner_id,
                workspace=str(workspace),
                scope_digest=scope_digest,
                expires_at=expires_at.isoformat(),
            )
        except BaseException:
            async with self._lock:
                self._pending_scopes.discard(scope_digest)
            raise
        async with self._lock:
            self._pending_scopes.discard(scope_digest)
            self._remove_expired()
            if scope_digest in self._scopes:
                raise ConflictError("This Docker session is already active")
            self._leases[token_digest] = lease
            self._scopes[scope_digest] = token_digest
            return token, lease

    async def authorize(self, token: str) -> Lease:
        digest = self._token_digest(token)
        async with self._lock:
            self._remove_expired()
            lease = self._leases.get(digest)
            if lease is None or not hmac.compare_digest(lease.token_digest, digest):
                raise LeaseError("Docker session authority is absent or expired")
            return lease

    async def _active_for_scope(
        self, *, session_id: str, owner_id: str, workspace: Path
    ) -> Lease | None:
        scope_digest = self._scope_digest(session_id, owner_id, workspace)
        async with self._lock:
            self._remove_expired()
            token_digest = self._scopes.get(scope_digest)
            if token_digest is None:
                return None
            return self._leases.get(token_digest)

    async def revoke(self, token: str) -> bool:
        digest = self._token_digest(token)
        async with self._lock:
            self._remove_expired()
            lease = self._leases.pop(digest, None)
            if lease is None:
                return False
            lease.revoked.set()
            self._scopes.pop(lease.scope_digest, None)
        try:
            await asyncio.to_thread(
                self._audit.write,
                "lease_revoked",
                session_id=lease.session_id,
                owner_id=lease.owner_id,
                workspace=str(lease.workspace),
                scope_digest=lease.scope_digest,
            )
        except (OSError, RuntimeError):
            pass
        return True
