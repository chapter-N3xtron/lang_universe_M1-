"""SQLite-backed single-use request lifecycle and restart recovery."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .errors import StateConflictError
from .models import HostOperationRequest, LifecycleState, SignedReceipt

_ALLOWED: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.REQUESTED: frozenset(
        {LifecycleState.CONFIRMING, LifecycleState.EXPIRED, LifecycleState.CANCELLED}
    ),
    LifecycleState.CONFIRMING: frozenset(
        {
            LifecycleState.CONFIRMED,
            LifecycleState.REJECTED,
            LifecycleState.EXPIRED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.CONFIRMED: frozenset(
        {LifecycleState.RUNNING, LifecycleState.CANCELLED, LifecycleState.EXPIRED}
    ),
    LifecycleState.RUNNING: frozenset(
        {
            LifecycleState.SUCCEEDED,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
            LifecycleState.PARTIAL,
            LifecycleState.UNCERTAIN,
        }
    ),
}


class StateStore:
    def __init__(self, path: Path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
        self.path = path
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS requests (
                    digest TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pid INTEGER,
                    receipt_json TEXT
                )"""
            )

    def create(
        self, request: HostOperationRequest
    ) -> tuple[LifecycleState, SignedReceipt | None]:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT request_json, state, receipt_json FROM requests WHERE digest=?",
                (request.digest,),
            ).fetchone()
            if row:
                stored = HostOperationRequest.model_validate_json(row["request_json"])
                if (
                    stored.thread_id != request.thread_id
                    or stored.interrupt_id != request.interrupt_id
                ):
                    connection.rollback()
                    raise StateConflictError(
                        "plan digest is already bound to another interrupt"
                    )
                connection.commit()
                receipt = (
                    SignedReceipt.model_validate_json(row["receipt_json"])
                    if row["receipt_json"]
                    else None
                )
                return LifecycleState(row["state"]), receipt
            active = connection.execute(
                "SELECT digest FROM requests WHERE state IN ('confirming','confirmed','running') LIMIT 1"
            ).fetchone()
            if active:
                connection.rollback()
                raise StateConflictError("another confirmation or execution is active")
            connection.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?, ?, NULL, NULL)",
                (
                    request.digest,
                    request.model_dump_json(),
                    LifecycleState.REQUESTED,
                    now,
                    now,
                ),
            )
            connection.commit()
        return LifecycleState.REQUESTED, None

    def claim_confirmation(self, digest: str) -> None:
        """Atomically consume the sole requested -> confirming transition."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT digest FROM requests "
                "WHERE state IN ('confirming','confirmed','running') AND digest<>? LIMIT 1",
                (digest,),
            ).fetchone()
            cursor = connection.execute(
                "UPDATE requests SET state='confirming', updated_at=? "
                "WHERE digest=? AND state='requested'",
                (datetime.now(UTC).isoformat(), digest),
            )
            if active or cursor.rowcount != 1:
                connection.rollback()
                raise StateConflictError(
                    "request is already consumed or another operation is active"
                )
            connection.commit()

    def transition(
        self, digest: str, target: LifecycleState, *, pid: int | None = None
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM requests WHERE digest=?", (digest,)
            ).fetchone()
            if not row:
                connection.rollback()
                raise StateConflictError("unknown request")
            current = LifecycleState(row["state"])
            if target not in _ALLOWED.get(current, frozenset()):
                connection.rollback()
                raise StateConflictError(
                    f"invalid lifecycle transition {current} -> {target}"
                )
            connection.execute(
                "UPDATE requests SET state=?, updated_at=?, pid=? WHERE digest=?",
                (target, datetime.now(UTC).isoformat(), pid, digest),
            )
            connection.commit()

    def finish(self, digest: str, receipt: SignedReceipt) -> None:
        target = receipt.receipt.terminal_status
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM requests WHERE digest=?", (digest,)
            ).fetchone()
            if not row:
                connection.rollback()
                raise StateConflictError("unknown request")
            current = LifecycleState(row["state"])
            if target not in _ALLOWED.get(current, frozenset()):
                connection.rollback()
                raise StateConflictError("terminal status is not monotonic")
            connection.execute(
                "UPDATE requests SET state=?, updated_at=?, pid=NULL, receipt_json=? WHERE digest=?",
                (
                    target,
                    datetime.now(UTC).isoformat(),
                    receipt.model_dump_json(),
                    digest,
                ),
            )
            connection.commit()

    def get(self, digest: str) -> tuple[LifecycleState, SignedReceipt | None] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state, receipt_json FROM requests WHERE digest=?", (digest,)
            ).fetchone()
        if not row:
            return None
        receipt = (
            SignedReceipt.model_validate_json(row["receipt_json"])
            if row["receipt_json"]
            else None
        )
        return LifecycleState(row["state"]), receipt

    def recover_after_restart(self) -> int:
        """Never replay: running/confirmed work becomes terminal uncertainty."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT digest, request_json FROM requests WHERE state IN ('confirmed','running')"
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE requests SET state='uncertain', updated_at=?, pid=NULL WHERE digest=?",
                    (datetime.now(UTC).isoformat(), row["digest"]),
                )
            connection.commit()
        return len(rows)

    def unreceipted_uncertain(self) -> tuple[HostOperationRequest, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT request_json FROM requests WHERE state='uncertain' AND receipt_json IS NULL"
            ).fetchall()
        return tuple(
            HostOperationRequest.model_validate_json(row["request_json"])
            for row in rows
        )

    def attach_recovery_receipt(self, digest: str, receipt: SignedReceipt) -> None:
        if receipt.receipt.terminal_status != LifecycleState.UNCERTAIN:
            raise StateConflictError("restart receipt must report uncertainty")
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE requests SET receipt_json=?, updated_at=? "
                "WHERE digest=? AND state='uncertain' AND receipt_json IS NULL",
                (receipt.model_dump_json(), datetime.now(UTC).isoformat(), digest),
            )
            if cursor.rowcount != 1:
                raise StateConflictError(
                    "uncertain request already receipted or unavailable"
                )
