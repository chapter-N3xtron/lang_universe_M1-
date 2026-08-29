"""Static safety checks for the unapplied Phase 5 PostgreSQL rollout artifact."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "deploy" / "postgres" / "phase5_least_privilege.sql"
README = ROOT / "deploy" / "postgres" / "README.md"

AGENT_SERVER_TABLES = {
    "assistant",
    "assistant_versions",
    "checkpoint_blobs",
    "checkpoint_delete_queue",
    "checkpoint_writes",
    "checkpoints",
    "cron",
    "run",
    "schema_migrations",
    "store",
    "thread",
    "thread_ttl",
}
CATALOG_TABLES = {
    "activity_intervals",
    "agent_participations",
    "artifacts",
    "projection_migrations",
    "session_artifact_links",
    "sessions",
    "summary_revisions",
    "tent_poles",
    "workspace_session_links",
    "workspaces",
}


def _sql() -> str:
    return SQL.read_text(encoding="utf-8")


def test_role_artifact_is_unwired_and_contains_no_authentication_material() -> None:
    text = _sql()
    assert "PREPARATION ARTIFACT ONLY" in text
    assert "\\set ON_ERROR_STOP on" in text
    assert not re.search(r"(?i)password|postgres(?:ql)?://|\.env", text)
    assert not re.search(r"(?im)^\s*(?:INSERT|UPDATE|DELETE|TRUNCATE|COPY)\b", text)


def test_roles_are_distinct_and_explicitly_unprivileged() -> None:
    text = _sql()
    assert text.count("CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE") == 2
    assert text.count("NOREPLICATION NOBYPASSRLS") == 2
    assert 'GRANT CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name"' in text
    assert 'GRANT CONNECT ON DATABASE :"database_name" TO :"session_catalog_role"' in text
    assert "GRANT ALL" not in text.upper()
    assert "ALTER DATABASE" not in text.upper()
    assert "REASSIGN OWNED" not in text.upper()


def test_ownership_allowlists_match_observed_schemas() -> None:
    text = _sql()
    agent_owned = set(
        re.findall(
            r'^ALTER TABLE public\.([a-z_]+) OWNER TO :"agent_server_role";$',
            text,
            flags=re.MULTILINE,
        )
    )
    catalog_owned = set(
        re.findall(
            r'^ALTER TABLE session_catalog\.([a-z_]+) OWNER TO :"session_catalog_role";$',
            text,
            flags=re.MULTILINE,
        )
    )
    assert agent_owned == AGENT_SERVER_TABLES
    assert catalog_owned == CATALOG_TABLES
    assert 'ALTER SCHEMA public OWNER TO :"agent_server_role";' in text
    assert 'ALTER SCHEMA session_catalog OWNER TO :"session_catalog_role";' in text


def test_documented_boundary_does_not_claim_sql_namespace_isolation() -> None:
    text = README.read_text(encoding="utf-8")
    assert "PostgreSQL grants cannot make" in text
    assert "default-deny capability authorization" in text
    assert "No browser, owner,\nJasper, Coder, Librarian, or OCR identity is a PostgreSQL role" in text
    assert "Do not add RLS" in text
