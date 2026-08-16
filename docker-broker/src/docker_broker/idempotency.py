from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any

from docker_broker.errors import ConflictError


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(path, flags, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077
            ):
                raise RuntimeError("idempotency database path is unsafe")
        finally:
            os.close(descriptor)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    scope_digest TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    PRIMARY KEY (scope_digest, request_id)
                )
                """
            )
        os.chmod(path, 0o600)

    def begin(
        self,
        scope_digest: str,
        request_id: str,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT fingerprint, status, response_json
                FROM operations
                WHERE scope_digest = ? AND request_id = ?
                """,
                (scope_digest, request_id),
            ).fetchone()
            if row:
                previous_fingerprint, status, response_json = row
                if previous_fingerprint != fingerprint:
                    raise ConflictError(
                        "request_id was already used for different operation inputs"
                    )
                if status == "succeeded" and response_json:
                    value = json.loads(response_json)
                    if isinstance(value, dict):
                        return value
                raise ConflictError(
                    "the prior operation outcome is in progress or unknown"
                )
            connection.execute(
                """
                INSERT INTO operations (
                    scope_digest, request_id, fingerprint, status, response_json
                ) VALUES (?, ?, ?, 'in_progress', NULL)
                """,
                (scope_digest, request_id, fingerprint),
            )
        return None

    def succeed(
        self,
        scope_digest: str,
        request_id: str,
        response: dict[str, Any],
    ) -> None:
        payload = json.dumps(response, separators=(",", ":"), sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE operations
                SET status = 'succeeded', response_json = ?
                WHERE scope_digest = ? AND request_id = ? AND status = 'in_progress'
                """,
                (payload, scope_digest, request_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("idempotency state transition failed")

    def mark_unknown(self, scope_digest: str, request_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE operations
                SET status = 'outcome_unknown'
                WHERE scope_digest = ? AND request_id = ? AND status = 'in_progress'
                """,
                (scope_digest, request_id),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=5, isolation_level=None)
