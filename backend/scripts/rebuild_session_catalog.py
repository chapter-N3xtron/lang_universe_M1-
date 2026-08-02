#!/usr/bin/env python3
"""Idempotently rebuild the session catalog through public Agent Server APIs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from langgraph_sdk import get_client
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.session_catalog import (
    DEFAULT_OWNER_ID,
    IDLE_CUTOFF_MINUTES,
    SCHEMA,
    ensure_catalog_schema,
    record_session_projection,
)


class SDKStoreAdapter:
    def __init__(self, client):
        self.client = client

    async def aput(self, namespace, key, value, *, index=None):
        await self.client.store.put_item(namespace, key, value, index=index)

    async def aget(self, namespace, key):
        return await self.client.store.get_item(namespace, key)


class RuntimeAdapter:
    def __init__(self, client):
        self.store = SDKStoreAdapter(client)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-url", default=os.getenv("AGENT_SERVER_URL", "http://127.0.0.1:8123")
    )
    parser.add_argument("--owner-id", default=DEFAULT_OWNER_ID)
    parser.add_argument("--tent-poles", type=Path, default=Path("tent_poles.json"))
    parser.add_argument("--verify-idempotent", action="store_true")
    return parser.parse_args()


async def all_threads(client) -> list[dict[str, Any]]:
    result = []
    offset = 0
    while True:
        page = await client.threads.search(
            metadata={"graph_id": "chat_ui"},
            limit=100,
            offset=offset,
            sort_by="created_at",
            sort_order="asc",
        )
        result.extend(page)
        if len(page) < 100:
            return result
        offset += len(page)


def _history_intervals(
    history: list[dict[str, Any]],
) -> list[tuple[datetime, datetime]]:
    timestamps = []
    for state in reversed(history):
        value = state.get("created_at")
        if value:
            timestamps.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    if not timestamps:
        return []
    intervals: list[list[datetime]] = [[timestamps[0], timestamps[0]]]
    for timestamp in timestamps[1:]:
        if (timestamp - intervals[-1][1]).total_seconds() <= IDLE_CUTOFF_MINUTES * 60:
            intervals[-1][1] = timestamp
        else:
            intervals.append([timestamp, timestamp])
    return [(start, end) for start, end in intervals]


async def import_thread(client, runtime, thread: dict[str, Any], owner_id: str) -> None:
    thread_id = str(thread["thread_id"])
    stored_item = await client.store.get_item((owner_id, "sessions"), thread_id)
    stored_session = dict(stored_item.get("value", {})) if stored_item else {}
    stored_status = stored_session.get("status", "open")
    if stored_status not in {"open", "closed", "forked"}:
        stored_status = "open"
    values = dict(thread.get("values") or {})
    metadata = dict(thread.get("metadata") or {})
    parent_session_id = stored_session.get("parent_session_id") or metadata.get(
        "parent_session_id"
    )
    parent_thread_id = stored_session.get("parent_thread_id") or metadata.get(
        "parent_thread_id"
    )
    values.update(
        {
            "thread_identity": thread_id,
            "user_identity": owner_id,
            "parent_session_id": parent_session_id,
            "parent_thread_id": parent_thread_id,
        }
    )
    await record_session_projection(
        values,
        {"configurable": {"thread_id": thread_id, "owner_id": owner_id}},
        runtime,
    )
    history = await client.threads.get_history(thread_id, limit=1000)
    intervals = _history_intervals(history)
    created_at = datetime.fromisoformat(
        str(thread["created_at"]).replace("Z", "+00:00")
    )
    updated_at = datetime.fromisoformat(
        str(thread["updated_at"]).replace("Z", "+00:00")
    )
    uri = os.environ["POSTGRES_URI"]
    async with await psycopg.AsyncConnection.connect(uri) as connection:  # noqa: SIM117
        async with connection.cursor() as cursor:
            await cursor.execute(
                f"""
                UPDATE {SCHEMA}.sessions
                SET created_at = %s, last_activity_at = %s, updated_at = %s,
                    status = %s, parent_session_id = %s, parent_thread_id = %s,
                    long_description = CASE WHEN %s THEN %s ELSE long_description END,
                    summary_version = CASE WHEN %s THEN %s ELSE summary_version END
                WHERE session_id = %s AND owner_id = %s
                """,
                (
                    created_at,
                    updated_at,
                    updated_at,
                    stored_status,
                    parent_session_id,
                    parent_thread_id,
                    bool(stored_session.get("summary_human_reviewed")),
                    stored_session.get("long_description", ""),
                    bool(stored_session.get("summary_human_reviewed")),
                    int(stored_session.get("summary_version", 1)),
                    thread_id,
                    owner_id,
                ),
            )
            if stored_session.get("summary_human_reviewed"):
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.summary_revisions (
                        owner_id, session_id, version, short_description,
                        long_description, source, human_locked
                    )
                    SELECT owner_id, session_id, summary_version,
                        short_description, long_description,
                        'human_close_review', true
                    FROM {SCHEMA}.sessions
                    WHERE session_id = %s AND owner_id = %s
                    ON CONFLICT (session_id, version) DO UPDATE SET
                        long_description = EXCLUDED.long_description,
                        source = EXCLUDED.source,
                        human_locked = true
                    """,
                    (thread_id, owner_id),
                )
            await cursor.execute(
                f"DELETE FROM {SCHEMA}.activity_intervals "
                "WHERE session_id = %s AND owner_id = %s",
                (thread_id, owner_id),
            )
            await cursor.executemany(
                f"""
                INSERT INTO {SCHEMA}.activity_intervals (
                    owner_id, session_id, started_at, ended_at, source
                ) VALUES (%s, %s, %s, %s, 'checkpoint_observed')
                """,
                [(owner_id, thread_id, start, end) for start, end in intervals],
            )


async def import_tent_poles(path: Path, owner_id: str) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text())
    records = payload if isinstance(payload, list) else payload.get("sessions", [])
    imported = 0
    uri = os.environ["POSTGRES_URI"]
    async with await psycopg.AsyncConnection.connect(uri) as connection:  # noqa: SIM117
        async with connection.cursor() as cursor:
            for record in records:
                session_id = str(
                    record.get("session_id") or record.get("thread_id") or ""
                )
                poles = record.get("tent_poles") or record.get("poles") or []
                if not session_id or not isinstance(poles, list):
                    continue
                for position, value in enumerate(poles):
                    await cursor.execute(
                        f"""
                        INSERT INTO {SCHEMA}.tent_poles (
                            owner_id, session_id, position, content, source
                        ) VALUES (%s, %s, %s, %s, 'legacy_import')
                        ON CONFLICT (session_id, position) DO UPDATE SET
                            content = EXCLUDED.content
                        """,
                        (owner_id, session_id, position, str(value)),
                    )
                    imported += 1
    return imported


async def projection_fingerprints(owner_id: str) -> dict[str, str]:
    """Hash each normalized table, excluding generated audit timestamps/IDs."""

    uri = os.environ["POSTGRES_URI"]
    async with await psycopg.AsyncConnection.connect(uri) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            tables = [
                "sessions",
                "workspaces",
                "workspace_session_links",
                "agent_participations",
                "activity_intervals",
                "artifacts",
                "session_artifact_links",
                "summary_revisions",
                "tent_poles",
            ]
            fingerprints: dict[str, str] = {}
            generated_columns = [
                "updated_at",
                "created_at",
                "linked_at",
                "first_seen_at",
                "last_seen_at",
                "interval_id",
            ]
            for table in tables:
                await cursor.execute(
                    f"""
                    SELECT COALESCE(
                        jsonb_agg(payload ORDER BY payload::text),
                        '[]'::jsonb
                    ) AS rows
                    FROM (
                        SELECT to_jsonb(record) - %s::text[] AS payload
                        FROM {SCHEMA}.{table} AS record
                        WHERE owner_id = %s
                    ) normalized
                    """,
                    (generated_columns, owner_id),
                )
                rows = (await cursor.fetchone())["rows"]
                fingerprints[table] = hashlib.sha256(
                    json.dumps(rows, sort_keys=True, default=str).encode()
                ).hexdigest()
    return fingerprints


def combined_fingerprint(fingerprints: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()


async def run(args: argparse.Namespace) -> None:
    if not os.getenv("POSTGRES_URI"):
        raise SystemExit(
            "POSTGRES_URI must identify the existing durable PostgreSQL service"
        )
    await ensure_catalog_schema()
    client = get_client(url=args.api_url)
    runtime = RuntimeAdapter(client)
    threads = await all_threads(client)
    for thread in threads:
        await import_thread(client, runtime, thread, args.owner_id)
    tent_poles = await import_tent_poles(args.tent_poles, args.owner_id)
    first_tables = await projection_fingerprints(args.owner_id)
    first = combined_fingerprint(first_tables)
    if args.verify_idempotent:
        for thread in threads:
            await import_thread(client, runtime, thread, args.owner_id)
        await import_tent_poles(args.tent_poles, args.owner_id)
        second_tables = await projection_fingerprints(args.owner_id)
        second = combined_fingerprint(second_tables)
        if first != second:
            changed = sorted(
                table
                for table in first_tables
                if first_tables[table] != second_tables[table]
            )
            raise SystemExit(
                f"Catalog rebuild was not idempotent; changed tables: {', '.join(changed)}"
            )
    uri = os.environ["POSTGRES_URI"]
    async with await psycopg.AsyncConnection.connect(uri) as connection:
        await connection.execute(
            f"""
            INSERT INTO {SCHEMA}.projection_migrations (migration_id, details)
            VALUES ('legacy-thread-catalog-v1', %s)
            ON CONFLICT (migration_id) DO UPDATE SET
                applied_at = now(), details = EXCLUDED.details
            """,
            (
                Jsonb(
                    {
                        "threads": len(threads),
                        "tent_poles": tent_poles,
                        "fingerprint": first,
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ),
            ),
        )
    print(
        json.dumps(
            {"threads": len(threads), "tent_poles": tent_poles, "fingerprint": first}
        )
    )


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
