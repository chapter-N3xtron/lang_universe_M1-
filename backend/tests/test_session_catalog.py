import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src import session_catalog_routes
from src.session_catalog import (
    DDL,
    _decode_cursor,
    _session_descriptions,
    _write_store_records,
    compile_filter_group,
    query_sessions,
)
from src.session_catalog_models import SessionQuery
from src.session_catalog_routes import _owner


def test_legacy_catalog_owner_remains_behind_authenticated_installation():
    assert _owner() == "local-owner-v1"
    assert _owner("local-owner-v1") == "local-owner-v1"
    with pytest.raises(HTTPException) as raised:
        _owner("other")
    assert raised.value.status_code == 403


def test_internal_client_preserves_installation_key_over_langsmith_key(monkeypatch):
    captured = {}

    def client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("INSTALLATION_OWNER_API_KEY", "installation-key")
    monkeypatch.setattr(session_catalog_routes, "get_client", client)
    session_catalog_routes._agent_server_client()
    assert captured == {
        "url": "http://127.0.0.1:8000",
        "api_key": None,
        "headers": {"X-Api-Key": "installation-key"},
    }


def test_nested_filter_tree_compiles_to_parameterized_sql():
    query = SessionQuery(
        owner_id="owner-1",
        filters={
            "combinator": "and",
            "rules": [
                {
                    "kind": "rule",
                    "field": "status",
                    "operator": "equals",
                    "value": "open",
                },
                {
                    "kind": "group",
                    "combinator": "or",
                    "rules": [
                        {
                            "kind": "rule",
                            "field": "agent",
                            "operator": "equals",
                            "value": "jasper",
                        },
                        {
                            "kind": "rule",
                            "field": "workspace",
                            "operator": "contains",
                            "value": "LangGraph",
                        },
                    ],
                },
            ],
        },
    )

    sql, parameters = compile_filter_group(query.filters)

    assert " AND " in sql
    assert " OR " in sql
    assert "EXISTS" in sql
    assert "LangGraph" not in sql
    assert parameters == ["open", "jasper", "LangGraph", "%LangGraph%"]


def test_browser_cannot_submit_raw_sql_or_unknown_fields():
    with pytest.raises(ValidationError):
        SessionQuery.model_validate(
            {
                "owner_id": "owner-1",
                "raw_sql": "DROP TABLE checkpoints",
                "filters": {
                    "rules": [
                        {
                            "kind": "rule",
                            "field": "checkpoint_blob",
                            "operator": "equals",
                            "value": "anything",
                        }
                    ]
                },
            }
        )


def test_invalid_cursor_fails_closed():
    with pytest.raises(ValueError, match="Invalid page cursor"):
        _decode_cursor("not-a-cursor")


def test_live_summary_uses_normal_response_without_an_extra_model_call():
    short, long = _session_descriptions(
        [
            {"role": "user", "content": "Plan a durable session library"},
            {
                "role": "assistant",
                "content": "One. Two. Three. Four. This fifth sentence is excluded.",
            },
        ]
    )

    assert short == "Plan a durable session library"
    assert long == "One. Two. Three. Four."


def test_projection_ddl_uses_only_application_owned_schema():
    assert "CREATE SCHEMA IF NOT EXISTS session_catalog" in DDL
    assert "CREATE TABLE IF NOT EXISTS session_catalog.sessions" in DDL
    assert "ALTER TABLE checkpoints" not in DDL
    assert "DELETE FROM checkpoints" not in DDL


@pytest.mark.asyncio
async def test_query_returns_empty_when_durable_database_is_not_configured(monkeypatch):
    monkeypatch.delenv("POSTGRES_URI", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    result = await query_sessions(SessionQuery(owner_id="owner-1"))

    assert result.total == 0
    assert result.rows == []


@pytest.mark.asyncio
async def test_projection_preserves_human_reviewed_store_lifecycle():
    class Store:
        def __init__(self):
            self.written = None

        async def aget(self, namespace, key):
            return {
                "value": {
                    "status": "closed",
                    "parent_session_id": "parent-session",
                    "tent_poles": ["Human reviewed"],
                    "summary_human_reviewed": True,
                    "long_description": "Reviewed summary",
                }
            }

        async def aput(self, namespace, key, value, *, index=None):
            self.written = value

    store = Store()
    runtime = type("Runtime", (), {"store": store})()
    await _write_store_records(
        runtime,
        owner_id="owner-1",
        thread_id="session-1",
        session={"status": "open", "long_description": "Updated summary"},
        workspace=None,
        artifacts=[],
    )

    assert store.written["status"] == "closed"
    assert store.written["parent_session_id"] == "parent-session"
    assert store.written["tent_poles"] == ["Human reviewed"]
    assert store.written["long_description"] == "Reviewed summary"
    assert store.written["summary_human_reviewed"] is True


@pytest.mark.asyncio
async def test_projection_repairs_missing_store_parent_from_authoritative_input():
    class Store:
        def __init__(self):
            self.written = None

        async def aget(self, namespace, key):
            return {"value": {"parent_session_id": None}}

        async def aput(self, namespace, key, value, *, index=None):
            self.written = value

    store = Store()
    runtime = type("Runtime", (), {"store": store})()
    await _write_store_records(
        runtime,
        owner_id="owner-1",
        thread_id="session-1",
        session={"parent_session_id": "parent-from-thread-metadata"},
        workspace=None,
        artifacts=[],
    )

    assert store.written["parent_session_id"] == "parent-from-thread-metadata"
