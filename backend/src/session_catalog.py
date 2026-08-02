"""Store-backed session memory with a rebuildable PostgreSQL query projection.

LangGraph checkpoints remain the conversation authority. LangGraph Store records
the durable owner-scoped session/workspace relationships. Tables in the
``session_catalog`` schema are an application-owned projection only; this module
never reads or writes LangGraph's internal persistence tables.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.session_catalog_models import (
    FilterGroup,
    FilterRule,
    SessionCatalogRow,
    SessionQuery,
    SessionQueryResponse,
)

logger = logging.getLogger(__name__)

SCHEMA = "session_catalog"
IDLE_CUTOFF_MINUTES = 15
DEFAULT_OWNER_ID = "local-owner-v1"


DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

CREATE TABLE IF NOT EXISTS {SCHEMA}.sessions (
    session_id text PRIMARY KEY,
    thread_id text NOT NULL UNIQUE,
    owner_id text NOT NULL,
    parent_session_id text,
    parent_thread_id text,
    status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'forked')),
    short_description text NOT NULL DEFAULT '',
    long_description text NOT NULL DEFAULT '',
    summary_version integer NOT NULL DEFAULT 1 CHECK (summary_version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS session_catalog_sessions_owner_activity_idx
    ON {SCHEMA}.sessions (owner_id, last_activity_at DESC, session_id);

CREATE TABLE IF NOT EXISTS {SCHEMA}.workspaces (
    workspace_id text PRIMARY KEY,
    owner_id text NOT NULL,
    name text NOT NULL,
    portable_identity jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    repository_binding_state text NOT NULL DEFAULT 'unbound'
        CHECK (repository_binding_state IN ('bound', 'unbound', 'unavailable')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.workspace_session_links (
    owner_id text NOT NULL,
    workspace_id text NOT NULL REFERENCES {SCHEMA}.workspaces(workspace_id)
        ON DELETE CASCADE,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'referenced',
    linked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, session_id)
);
CREATE INDEX IF NOT EXISTS session_catalog_workspace_links_session_idx
    ON {SCHEMA}.workspace_session_links (session_id, workspace_id);

CREATE TABLE IF NOT EXISTS {SCHEMA}.agent_participations (
    owner_id text NOT NULL,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    profile_id text NOT NULL,
    profile_version text NOT NULL DEFAULT '1',
    role text NOT NULL DEFAULT 'participant',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, profile_id, profile_version, role)
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.activity_intervals (
    interval_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id text NOT NULL,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    started_at timestamptz NOT NULL,
    ended_at timestamptz NOT NULL,
    source text NOT NULL DEFAULT 'observed',
    corrected boolean NOT NULL DEFAULT false,
    CHECK (ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS session_catalog_activity_session_idx
    ON {SCHEMA}.activity_intervals (session_id, ended_at DESC);

CREATE TABLE IF NOT EXISTS {SCHEMA}.artifacts (
    artifact_id text PRIMARY KEY,
    owner_id text NOT NULL,
    parent_artifact_id text,
    title text NOT NULL,
    renderer text NOT NULL,
    source_message_id text,
    artifact_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS {SCHEMA}.session_artifact_links (
    owner_id text NOT NULL,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    artifact_id text NOT NULL REFERENCES {SCHEMA}.artifacts(artifact_id)
        ON DELETE CASCADE,
    relationship text NOT NULL DEFAULT 'created',
    position integer NOT NULL DEFAULT 0,
    linked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, artifact_id)
);
CREATE INDEX IF NOT EXISTS session_catalog_artifact_links_session_idx
    ON {SCHEMA}.session_artifact_links (session_id, position, linked_at);

CREATE TABLE IF NOT EXISTS {SCHEMA}.summary_revisions (
    owner_id text NOT NULL,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    version integer NOT NULL,
    short_description text NOT NULL,
    long_description text NOT NULL,
    source text NOT NULL,
    human_locked boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, version)
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.tent_poles (
    owner_id text NOT NULL,
    session_id text NOT NULL REFERENCES {SCHEMA}.sessions(session_id)
        ON DELETE CASCADE,
    position integer NOT NULL,
    content text NOT NULL,
    source text NOT NULL DEFAULT 'human_reviewed',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, position)
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.projection_migrations (
    migration_id text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    details jsonb NOT NULL DEFAULT '{{}}'::jsonb
);
"""


def _database_uri() -> str | None:
    return os.getenv("POSTGRES_URI") or os.getenv("DATABASE_URL")


async def ensure_catalog_schema() -> bool:
    """Create only application-owned projection tables, if PostgreSQL is configured."""

    uri = _database_uri()
    if not uri:
        return False
    async with await psycopg.AsyncConnection.connect(uri) as connection:
        await connection.execute(DDL)
    return True


def _message_role(message: Any) -> str:
    if isinstance(message, Mapping):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "type", ""))


def _message_content(message: Any) -> str:
    content = (
        message.get("content", "")
        if isinstance(message, Mapping)
        else getattr(message, "content", "")
    )
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, Mapping) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return " ".join(parts).strip()
    return ""


def _clean_description(text: str, *, maximum: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


def _session_descriptions(messages: Iterable[Any]) -> tuple[str, str]:
    human: list[str] = []
    assistant: list[str] = []
    for message in messages:
        role = _message_role(message)
        content = _message_content(message)
        if not content:
            continue
        if role in {"human", "user"}:
            human.append(content)
        elif role in {"ai", "assistant"}:
            assistant.append(content)
    short = _clean_description(human[0] if human else "Untitled session", maximum=140)
    source = assistant[-1] if assistant else (human[-1] if human else short)
    sentences = re.split(r"(?<=[.!?])\s+", source)
    long = _clean_description(" ".join(sentences[:4]), maximum=900)
    return short, long


def _owner_and_thread(
    state: Mapping[str, Any], config: RunnableConfig
) -> tuple[str, str]:
    configurable = config.get("configurable", {})
    owner_id = str(
        state.get("user_identity")
        or configurable.get("user_id")
        or configurable.get("owner_id")
        or DEFAULT_OWNER_ID
    )
    thread_id = str(state.get("thread_identity") or configurable.get("thread_id") or "")
    return owner_id[:128], thread_id[:128]


def _workspace_record(workspace: str | None, owner_id: str) -> dict[str, Any] | None:
    if not workspace:
        return None
    normalized = str(Path(workspace).expanduser().resolve(strict=False))
    workspace_id = hashlib.sha256(f"{owner_id}\0{normalized}".encode()).hexdigest()[:32]
    return {
        "workspace_id": workspace_id,
        "name": Path(normalized).name or normalized,
        "repository_binding_state": "bound"
        if Path(normalized).exists()
        else "unavailable",
        "portable_identity": {
            "kind": "local_path_binding",
            "display_name": Path(normalized).name,
        },
    }


async def _write_store_records(
    runtime: Runtime,
    *,
    owner_id: str,
    thread_id: str,
    session: dict[str, Any],
    workspace: dict[str, Any] | None,
    artifacts: list[dict[str, Any]],
) -> None:
    store = getattr(runtime, "store", None)
    if store is None:
        return
    existing_value: dict[str, Any] = {}
    get_item = getattr(store, "aget", None)
    if get_item is not None:
        existing = await get_item((owner_id, "sessions"), thread_id)
        if isinstance(existing, Mapping):
            existing_value = dict(existing.get("value", existing))
        elif existing is not None and isinstance(
            getattr(existing, "value", None), Mapping
        ):
            existing_value = dict(existing.value)
    stored_session = {**existing_value, **session}
    for governed_field in (
        "status",
        "parent_session_id",
        "parent_thread_id",
        "tent_poles",
        "summary_human_reviewed",
    ):
        if existing_value.get(governed_field) is not None:
            stored_session[governed_field] = existing_value[governed_field]
    if existing_value.get("summary_human_reviewed"):
        stored_session["long_description"] = existing_value.get(
            "long_description", stored_session.get("long_description", "")
        )
        stored_session["summary_version"] = existing_value.get(
            "summary_version", stored_session.get("summary_version", 1)
        )
    await store.aput((owner_id, "sessions"), thread_id, stored_session, index=False)
    if workspace:
        await store.aput(
            (owner_id, "workspaces"), workspace["workspace_id"], workspace, index=False
        )
        await store.aput(
            (owner_id, "workspace-session-links"),
            f"{workspace['workspace_id']}:{thread_id}",
            {
                "workspace_id": workspace["workspace_id"],
                "session_id": thread_id,
                "role": "referenced",
            },
            index=False,
        )
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id", ""))
        if artifact_id:
            await store.aput(
                (owner_id, "session-artifacts", thread_id),
                artifact_id,
                artifact,
                index=False,
            )


async def record_session_projection(
    state: Mapping[str, Any], config: RunnableConfig, runtime: Runtime
) -> None:
    """Persist one completed graph turn into Store and the query projection."""

    owner_id, thread_id = _owner_and_thread(state, config)
    if not thread_id:
        logger.warning("Skipping session record without a thread identity")
        return
    now = datetime.now(UTC)
    messages = list(state.get("messages", []))
    short, long = _session_descriptions(messages)
    active_agent = str(
        state.get("active_agent") or state.get("target_agent") or "jasper"
    )
    workspace = _workspace_record(state.get("workspace"), owner_id)
    artifacts = [
        artifact
        for artifact in state.get("visual_artifacts", [])
        if isinstance(artifact, dict) and artifact.get("artifact_id")
    ]
    session = {
        "session_id": thread_id,
        "thread_id": thread_id,
        "owner_id": owner_id,
        "status": "open",
        "short_description": short,
        "long_description": long,
        "last_activity_at": now.isoformat(),
        "summary_source": "normal_agent_response",
        "summary_version": 1,
        "participating_agent": active_agent,
        "parent_session_id": state.get("parent_session_id"),
        "parent_thread_id": state.get("parent_thread_id"),
    }
    uri = _database_uri()
    if not uri:
        await _write_store_records(
            runtime,
            owner_id=owner_id,
            thread_id=thread_id,
            session=session,
            workspace=workspace,
            artifacts=artifacts,
        )
        return
    await ensure_catalog_schema()
    async with await psycopg.AsyncConnection.connect(uri) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT s.long_description, s.summary_version,
                    EXISTS (
                        SELECT 1 FROM {SCHEMA}.summary_revisions sr
                        WHERE sr.session_id = s.session_id
                            AND sr.owner_id = s.owner_id
                            AND sr.human_locked
                    ) AS human_locked
                FROM {SCHEMA}.sessions s
                WHERE s.session_id = %s AND s.owner_id = %s
                """,
                (thread_id, owner_id),
            )
            previous = await cursor.fetchone()
            if previous and previous["human_locked"]:
                long = previous["long_description"]
            summary_version = int(previous["summary_version"]) if previous else 1
            summary_changed = bool(previous and previous["long_description"] != long)
            if summary_changed:
                summary_version += 1
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.sessions (
                    session_id, thread_id, owner_id, short_description,
                    long_description, summary_version, last_activity_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    short_description = EXCLUDED.short_description,
                    long_description = EXCLUDED.long_description,
                    summary_version = EXCLUDED.summary_version,
                    last_activity_at = EXCLUDED.last_activity_at,
                    updated_at = now()
                WHERE {SCHEMA}.sessions.owner_id = EXCLUDED.owner_id
                """,
                (thread_id, thread_id, owner_id, short, long, summary_version, now),
            )
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.summary_revisions (
                    owner_id, session_id, version, short_description,
                    long_description, source
                ) VALUES (%s, %s, %s, %s, %s, 'normal_agent_response')
                ON CONFLICT (session_id, version) DO NOTHING
                """,
                (owner_id, thread_id, summary_version, short, long),
            )
            await cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.agent_participations (
                    owner_id, session_id, profile_id, last_seen_at
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id, profile_id, profile_version, role)
                DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
                """,
                (owner_id, thread_id, active_agent, now),
            )
            await _record_activity(cursor, owner_id, thread_id, now)
            if workspace:
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.workspaces (
                        workspace_id, owner_id, name, portable_identity,
                        repository_binding_state
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (workspace_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        portable_identity = EXCLUDED.portable_identity,
                        repository_binding_state = EXCLUDED.repository_binding_state,
                        updated_at = now()
                    WHERE {SCHEMA}.workspaces.owner_id = EXCLUDED.owner_id
                    """,
                    (
                        workspace["workspace_id"],
                        owner_id,
                        workspace["name"],
                        Jsonb(workspace["portable_identity"]),
                        workspace["repository_binding_state"],
                    ),
                )
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.workspace_session_links (
                        owner_id, workspace_id, session_id
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (workspace_id, session_id) DO NOTHING
                    """,
                    (owner_id, workspace["workspace_id"], thread_id),
                )
            for position, artifact in enumerate(artifacts):
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.artifacts (
                        artifact_id, owner_id, parent_artifact_id,
                        title, renderer, source_message_id, artifact_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (artifact_id) DO NOTHING
                    """,
                    (
                        artifact["artifact_id"],
                        owner_id,
                        artifact.get("parent_artifact_id"),
                        str(artifact.get("title", "Untitled visual"))[:160],
                        str(artifact.get("renderer", "unknown"))[:80],
                        artifact.get("source_message_id"),
                        Jsonb(artifact),
                    ),
                )
                await cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.session_artifact_links (
                        owner_id, session_id, artifact_id, relationship, position
                    ) VALUES (%s, %s, %s, 'created', %s)
                    ON CONFLICT (session_id, artifact_id) DO NOTHING
                    """,
                    (
                        owner_id,
                        thread_id,
                        artifact["artifact_id"],
                        position,
                    ),
                )

    session["long_description"] = long
    session["summary_version"] = summary_version
    await _write_store_records(
        runtime,
        owner_id=owner_id,
        thread_id=thread_id,
        session=session,
        workspace=workspace,
        artifacts=artifacts,
    )


async def _record_activity(
    cursor, owner_id: str, session_id: str, now: datetime
) -> None:
    await cursor.execute(
        f"""
        SELECT interval_id, ended_at
        FROM {SCHEMA}.activity_intervals
        WHERE session_id = %s AND owner_id = %s
        ORDER BY ended_at DESC LIMIT 1
        FOR UPDATE
        """,
        (session_id, owner_id),
    )
    last = await cursor.fetchone()
    if last and (now - last["ended_at"]).total_seconds() <= IDLE_CUTOFF_MINUTES * 60:
        await cursor.execute(
            f"UPDATE {SCHEMA}.activity_intervals SET ended_at = %s "
            "WHERE interval_id = %s",
            (now, last["interval_id"]),
        )
    else:
        await cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.activity_intervals (
                owner_id, session_id, started_at, ended_at
            ) VALUES (%s, %s, %s, %s)
            """,
            (owner_id, session_id, now, now),
        )


FIELD_EXPRESSIONS = {
    "created_at": "s.created_at",
    "last_activity_at": "s.last_activity_at",
    "status": "s.status",
    "active_minutes": "s.active_minutes",
    "has_visuals": "(s.visual_count > 0)",
    "text": "(s.short_description || ' ' || s.long_description)",
}
SORT_EXPRESSIONS = {
    "created_at": "s.created_at",
    "last_activity_at": "s.last_activity_at",
    "short_description": "s.short_description",
    "active_minutes": "s.active_minutes",
    "status": "s.status",
    "visual_count": "s.visual_count",
}


def _field_expression(field: str) -> str:
    if field == "workspace":
        return (
            f"EXISTS (SELECT 1 FROM {SCHEMA}.workspace_session_links wsl "
            f"JOIN {SCHEMA}.workspaces w ON w.workspace_id = wsl.workspace_id "
            "WHERE wsl.session_id = s.session_id AND w.owner_id = s.owner_id "
            "AND (w.workspace_id = %s OR w.name ILIKE %s))"
        )
    if field == "agent":
        return (
            f"EXISTS (SELECT 1 FROM {SCHEMA}.agent_participations ap "
            "WHERE ap.session_id = s.session_id AND ap.owner_id = s.owner_id "
            "AND ap.profile_id = %s)"
        )
    return FIELD_EXPRESSIONS[field]


def _compile_rule(rule: FilterRule) -> tuple[str, list[Any]]:
    field = rule.field
    operator = rule.operator
    value = rule.value
    if field == "workspace":
        if operator not in {"equals", "contains"} or not isinstance(value, str):
            raise ValueError("workspace supports equals or contains with a string")
        expression = _field_expression(field)
        return expression, [value, f"%{_escape_like(value)}%"]
    if field == "agent":
        if operator != "equals" or not isinstance(value, str):
            raise ValueError("agent supports equals with a string")
        return _field_expression(field), [value]

    expression = _field_expression(field)
    if operator in {"isNull", "isNotNull"}:
        return f"{expression} IS {'NOT ' if operator == 'isNotNull' else ''}NULL", []
    if operator in {"contains", "doesNotContain", "beginsWith", "endsWith"}:
        if not isinstance(value, str):
            raise ValueError(f"{operator} requires a string")
        pattern = {
            "contains": f"%{_escape_like(value)}%",
            "doesNotContain": f"%{_escape_like(value)}%",
            "beginsWith": f"{_escape_like(value)}%",
            "endsWith": f"%{_escape_like(value)}",
        }[operator]
        comparison = "NOT ILIKE" if operator == "doesNotContain" else "ILIKE"
        return f"{expression} {comparison} %s ESCAPE '\\'", [pattern]
    if operator in {"in", "notIn"}:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{operator} requires a non-empty list")
        placeholders = ", ".join(["%s"] * len(value))
        return (
            f"{expression} {'NOT ' if operator == 'notIn' else ''}IN ({placeholders})",
            list(value),
        )
    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("between requires exactly two values")
        return f"{expression} BETWEEN %s AND %s", list(value)
    comparisons = {
        "equals": "=",
        "notEquals": "<>",
        "greaterThan": ">",
        "greaterThanOrEqual": ">=",
        "lessThan": "<",
        "lessThanOrEqual": "<=",
    }
    comparison = comparisons.get(operator)
    if comparison is None or value is None or isinstance(value, list):
        raise ValueError(f"Unsupported value for {field} {operator}")
    return f"{expression} {comparison} %s", [value]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def compile_filter_group(group: FilterGroup) -> tuple[str, list[Any]]:
    parts: list[str] = []
    parameters: list[Any] = []
    for child in group.rules:
        if isinstance(child, FilterGroup):
            sql, values = compile_filter_group(child)
        else:
            sql, values = _compile_rule(child)
        if sql:
            parts.append(f"({sql})")
            parameters.extend(values)
    if not parts:
        return "", []
    joined = f" {group.combinator.upper()} ".join(parts)
    return (f"NOT ({joined})" if group.not_ else joined), parameters


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=="))
        offset = int(payload["offset"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid page cursor") from exc
    if offset < 0:
        raise ValueError("Invalid page cursor")
    return offset


def _encode_cursor(offset: int) -> str:
    raw = json.dumps({"offset": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def query_sessions(query: SessionQuery) -> SessionQueryResponse:
    uri = _database_uri()
    if not uri:
        return SessionQueryResponse(rows=[], total=0)
    await ensure_catalog_schema()
    filter_sql, parameters = compile_filter_group(query.filters)
    where_parts = ["s.owner_id = %s"]
    where_parameters: list[Any] = [query.owner_id]
    if filter_sql:
        where_parts.append(filter_sql)
        where_parameters.extend(parameters)
    if query.search:
        escaped = f"%{_escape_like(query.search)}%"
        where_parts.append(
            "(s.short_description ILIKE %s ESCAPE '\\' "
            "OR s.long_description ILIKE %s ESCAPE '\\')"
        )
        where_parameters.extend([escaped, escaped])
    where_sql = " AND ".join(f"({part})" for part in where_parts)
    ordering = ", ".join(
        f"{SORT_EXPRESSIONS[item.field]} {item.direction.upper()}"
        for item in query.sort
    )
    ordering = f"{ordering}, s.session_id ASC" if ordering else "s.session_id ASC"
    offset = _decode_cursor(query.cursor)
    base_cte = f"""
        WITH session_rows AS (
            SELECT raw.*,
                COALESCE((SELECT floor(sum(extract(epoch FROM (ended_at - started_at))) / 60)::int
                    FROM {SCHEMA}.activity_intervals ai
                    WHERE ai.session_id = raw.session_id), 0) AS active_minutes,
                (SELECT count(*)::int FROM {SCHEMA}.session_artifact_links sal
                    WHERE sal.session_id = raw.session_id) AS visual_count
            FROM {SCHEMA}.sessions raw
        )
    """
    select_sql = (
        base_cte
        + f"""
        SELECT s.*,
            COALESCE((SELECT jsonb_agg(jsonb_build_object(
                'workspace_id', w.workspace_id,
                'name', w.name,
                'repository_binding_state', w.repository_binding_state
            ) ORDER BY w.name)
                FROM {SCHEMA}.workspace_session_links wsl
                JOIN {SCHEMA}.workspaces w ON w.workspace_id = wsl.workspace_id
                WHERE wsl.session_id = s.session_id), '[]'::jsonb) AS workspaces,
            COALESCE((SELECT jsonb_agg(jsonb_build_object(
                'profile_id', ap.profile_id,
                'profile_version', ap.profile_version,
                'role', ap.role
            ) ORDER BY ap.first_seen_at)
                FROM {SCHEMA}.agent_participations ap
                WHERE ap.session_id = s.session_id), '[]'::jsonb) AS agents
        FROM session_rows s
        WHERE {where_sql}
        ORDER BY {ordering}
        LIMIT %s OFFSET %s
    """
    )
    count_sql = (
        base_cte + f"SELECT count(*) AS total FROM session_rows s WHERE {where_sql}"
    )
    async with await psycopg.AsyncConnection.connect(uri) as connection:  # noqa: SIM117
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(count_sql, where_parameters)
            total = int((await cursor.fetchone())["total"])
            await cursor.execute(
                select_sql, [*where_parameters, query.page_size, offset]
            )
            raw_rows = await cursor.fetchall()
    rows = [
        SessionCatalogRow(
            session_id=row["session_id"],
            thread_id=row["thread_id"],
            parent_session_id=row["parent_session_id"],
            parent_thread_id=row["parent_thread_id"],
            created_at=row["created_at"],
            last_activity_at=row["last_activity_at"],
            short_description=row["short_description"],
            long_description=row["long_description"],
            active_minutes=row["active_minutes"],
            status=row["status"],
            workspaces=row["workspaces"],
            agents=row["agents"],
            visual_count=row["visual_count"],
            has_visuals=row["visual_count"] > 0,
            summary_version=row["summary_version"],
        )
        for row in raw_rows
    ]
    next_offset = offset + len(rows)
    return SessionQueryResponse(
        rows=rows,
        total=total,
        next_cursor=_encode_cursor(next_offset) if next_offset < total else None,
    )
