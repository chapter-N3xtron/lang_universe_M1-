"""Supported Agent Server custom routes for the visual session library."""

from __future__ import annotations

import os
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, Query
from langgraph_sdk import get_client
from psycopg.rows import dict_row

from src.session_catalog import SCHEMA, ensure_catalog_schema, query_sessions
from src.session_catalog_models import (
    SavedViewInput,
    SessionCloseInput,
    SessionForkInput,
    SessionQuery,
)

router = APIRouter(prefix="/session-catalog", tags=["session-catalog"])


def _database_uri() -> str:
    uri = os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")
    if not uri:
        raise HTTPException(503, "The durable session catalog is unavailable.")
    return uri


def _agent_server_client():
    port = os.getenv("PORT", "8000")
    return get_client(url=f"http://127.0.0.1:{port}")


@router.post("/query")
async def session_catalog_query(query: SessionQuery) -> dict[str, Any]:
    """Validate and compile a typed rule tree; browser SQL is never accepted."""

    try:
        result = await query_sessions(query)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/{session_id}")
async def session_detail(
    session_id: str, owner_id: str = Query(min_length=1, max_length=128)
) -> dict[str, Any]:
    """Return owner-scoped review data without reading checkpoint internals."""

    await ensure_catalog_schema()
    async with await psycopg.AsyncConnection.connect(_database_uri()) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT session_id, thread_id, status, short_description,
                    long_description, parent_session_id, parent_thread_id,
                    created_at, last_activity_at,
                    COALESCE((SELECT floor(sum(extract(epoch FROM (ended_at - started_at))) / 60)::int
                        FROM {SCHEMA}.activity_intervals ai
                        WHERE ai.session_id = s.session_id), 0) AS active_minutes
                FROM {SCHEMA}.sessions s
                WHERE session_id = %s AND owner_id = %s
                """,
                (session_id, owner_id),
            )
            session = await cursor.fetchone()
            if not session:
                raise HTTPException(404, "Session not found.")
            await cursor.execute(
                f"""
                SELECT content FROM {SCHEMA}.tent_poles
                WHERE session_id = %s AND owner_id = %s
                ORDER BY position
                """,
                (session_id, owner_id),
            )
            tent_poles = [row["content"] for row in await cursor.fetchall()]
    return {
        **session,
        "created_at": session["created_at"].isoformat(),
        "last_activity_at": session["last_activity_at"].isoformat(),
        "tent_poles": tent_poles,
    }


@router.get("/{session_id}/artifacts")
async def session_artifacts(
    session_id: str, owner_id: str = Query(min_length=1, max_length=128)
) -> dict[str, Any]:
    await ensure_catalog_schema()
    async with await psycopg.AsyncConnection.connect(_database_uri()) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT a.artifact_payload, sal.relationship, sal.position, sal.linked_at
                FROM {SCHEMA}.session_artifact_links sal
                JOIN {SCHEMA}.artifacts a ON a.artifact_id = sal.artifact_id
                JOIN {SCHEMA}.sessions s ON s.session_id = sal.session_id
                WHERE sal.session_id = %s AND sal.owner_id = %s AND s.owner_id = %s
                ORDER BY sal.position, sal.linked_at, a.artifact_id
                """,
                (session_id, owner_id, owner_id),
            )
            rows = await cursor.fetchall()
    return {
        "artifacts": [
            {
                "artifact": row["artifact_payload"],
                "relationship": row["relationship"],
                "position": row["position"],
                "linked_at": row["linked_at"].isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/{session_id}/close")
async def close_session(session_id: str, body: SessionCloseInput) -> dict[str, Any]:
    await ensure_catalog_schema()
    async with await psycopg.AsyncConnection.connect(_database_uri()) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                UPDATE {SCHEMA}.sessions
                SET status = 'closed', closed_at = now(),
                    long_description = COALESCE(%s, long_description),
                    summary_version = CASE WHEN %s::text IS NULL THEN summary_version
                        ELSE summary_version + 1 END,
                    updated_at = now()
                WHERE session_id = %s AND owner_id = %s
                RETURNING *
                """,
                (body.summary, body.summary, session_id, body.owner_id),
            )
            session = await cursor.fetchone()
            if not session:
                raise HTTPException(404, "Session not found.")
            if body.tent_poles:
                await cursor.execute(
                    f"DELETE FROM {SCHEMA}.tent_poles "
                    "WHERE session_id = %s AND owner_id = %s",
                    (session_id, body.owner_id),
                )
                await cursor.executemany(
                    f"""
                    INSERT INTO {SCHEMA}.tent_poles (
                        owner_id, session_id, position, content
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    [
                        (body.owner_id, session_id, index, value)
                        for index, value in enumerate(body.tent_poles)
                    ],
                )
            if body.summary is not None:
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.summary_revisions (
                        owner_id, session_id, version, short_description,
                        long_description, source, human_locked
                    ) VALUES (%s, %s, %s, %s, %s, 'human_close_review', true)
                    ON CONFLICT (session_id, version) DO UPDATE SET
                        long_description = EXCLUDED.long_description,
                        source = EXCLUDED.source,
                        human_locked = true
                    """,
                    (
                        body.owner_id,
                        session_id,
                        session["summary_version"],
                        session["short_description"],
                        body.summary,
                    ),
                )
    client = _agent_server_client()
    item = await client.store.get_item((body.owner_id, "sessions"), session_id)
    value = dict(item.get("value", {})) if item else {}
    value.update(
        {
            "status": "closed",
            "long_description": body.summary or value.get("long_description", ""),
            "tent_poles": body.tent_poles,
            "summary_human_reviewed": body.summary is not None,
            "summary_version": session["summary_version"],
        }
    )
    await client.store.put_item(
        (body.owner_id, "sessions"), session_id, value, index=False
    )
    return {"session_id": session_id, "status": "closed"}


@router.post("/{session_id}/fork")
async def fork_session(session_id: str, body: SessionForkInput) -> dict[str, Any]:
    """Use Agent Server thread APIs; prior tools are never replayed."""

    await ensure_catalog_schema()
    async with await psycopg.AsyncConnection.connect(_database_uri()) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"SELECT * FROM {SCHEMA}.sessions "
                "WHERE session_id = %s AND owner_id = %s",
                (session_id, body.owner_id),
            )
            source = await cursor.fetchone()
    if not source:
        raise HTTPException(404, "Session not found.")

    client = _agent_server_client()
    metadata = {
        "graph_id": "chat_ui",
        "owner_id": body.owner_id,
        "parent_thread_id": source["thread_id"],
        "parent_session_id": session_id,
    }
    if body.checkpoint_id:
        checkpoint = await client.threads.get_state(
            source["thread_id"], checkpoint_id=body.checkpoint_id
        )
        values = checkpoint.get("values", {})
        copied = await client.threads.create(
            graph_id="chat_ui",
            metadata=metadata,
            supersteps=[{"updates": [{"values": values, "as_node": "__input__"}]}],
        )
    else:
        copied = await client.threads.copy(source["thread_id"])
        if not isinstance(copied, dict) or not copied.get("thread_id"):
            raise HTTPException(502, "Agent Server did not return the copied thread.")
        await client.threads.update(copied["thread_id"], metadata=metadata)
    new_thread_id = str(copied["thread_id"])

    async with await psycopg.AsyncConnection.connect(_database_uri()) as connection:  # noqa: SIM117
        async with connection.cursor() as cursor:
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.sessions (
                    session_id, thread_id, owner_id, parent_session_id,
                    parent_thread_id, status, short_description,
                    long_description, summary_version
                ) VALUES (%s, %s, %s, %s, %s, 'forked', %s, %s, %s)
                """,
                (
                    new_thread_id,
                    new_thread_id,
                    body.owner_id,
                    session_id,
                    source["thread_id"],
                    source["short_description"],
                    source["long_description"],
                    source["summary_version"],
                ),
            )
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.workspace_session_links (
                    owner_id, workspace_id, session_id, role
                )
                SELECT owner_id, workspace_id, %s, 'inherited'
                FROM {SCHEMA}.workspace_session_links
                WHERE session_id = %s AND owner_id = %s
                """,
                (new_thread_id, session_id, body.owner_id),
            )
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.agent_participations (
                    owner_id, session_id, profile_id, profile_version, role,
                    first_seen_at, last_seen_at
                )
                SELECT owner_id, %s, profile_id, profile_version, role,
                    first_seen_at, last_seen_at
                FROM {SCHEMA}.agent_participations
                WHERE session_id = %s AND owner_id = %s
                """,
                (new_thread_id, session_id, body.owner_id),
            )
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.session_artifact_links (
                    owner_id, session_id, artifact_id, relationship, position
                )
                SELECT owner_id, %s, artifact_id, 'inherited', position
                FROM {SCHEMA}.session_artifact_links
                WHERE session_id = %s AND owner_id = %s
                """,
                (new_thread_id, session_id, body.owner_id),
            )

    parent_item = await client.store.get_item((body.owner_id, "sessions"), session_id)
    parent_value = dict(parent_item.get("value", {})) if parent_item else {}
    parent_value.update(
        {
            "session_id": new_thread_id,
            "thread_id": new_thread_id,
            "status": "forked",
            "parent_session_id": session_id,
            "parent_thread_id": source["thread_id"],
        }
    )
    await client.store.put_item(
        (body.owner_id, "sessions"), new_thread_id, parent_value, index=False
    )
    return {
        "session_id": new_thread_id,
        "thread_id": new_thread_id,
        "parent_session_id": session_id,
        "checkpoint_id": body.checkpoint_id,
    }


@router.get("/views/saved")
async def list_saved_views(
    owner_id: str = Query(min_length=1, max_length=128),
) -> dict[str, Any]:
    result = await _agent_server_client().store.search_items(
        (owner_id, "session-library-views"), limit=100
    )
    return {"views": [item["value"] for item in result.get("items", [])]}


@router.put("/views/saved/{view_id}")
async def save_view(view_id: str, body: SavedViewInput) -> dict[str, Any]:
    if view_id != body.view_id or body.query.owner_id != body.owner_id:
        raise HTTPException(422, "Saved-view ownership or identity does not match.")
    value = body.model_dump(mode="json", by_alias=True)
    await _agent_server_client().store.put_item(
        (body.owner_id, "session-library-views"), view_id, value, index=False
    )
    return value


@router.delete("/views/saved/{view_id}")
async def delete_saved_view(
    view_id: str, owner_id: str = Query(min_length=1, max_length=128)
) -> dict[str, bool]:
    await _agent_server_client().store.delete_item(
        (owner_id, "session-library-views"), view_id
    )
    return {"deleted": True}
