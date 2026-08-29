"""Synthetic, one-dimension-at-a-time Phase 5 contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from langgraph.store.memory import InMemoryStore

import src.phase5_capabilities as phase5
from src.phase5_capabilities import (
    Authority,
    CapabilityError,
    Delegation,
    StoreCapabilities,
    documentation_namespace,
    issue_token,
    lexical_rank,
    memory_namespace,
    verify_token,
)

AUTH = Authority(
    "tenant-1",
    "owner-1",
    memory_grants=frozenset(
        {"read", "write", "delete", "restore", "permanent-delete", "audit"}
    ),
    corpus_read_grants=frozenset({"installation-docs"}),
)
NOW = datetime(2026, 1, 1, tzinfo=UTC)
PROV = {"source_type": "owner-statement", "source_id": "turn-1", "actor": "jasper"}
DOC_PROV = {
    "document_id": "doc-1",
    "locator": "p1",
    "title": "Guide",
    "source_revision": "r1",
    "digest": "abc",
    "source_status": "active",
    "source_type": "owner-upload",
}


def test_namespaces_separate_families_and_reject_one_changed_dimension():
    assert memory_namespace(AUTH, "task-outcomes")[2] == "cross-session-memory"
    assert (
        documentation_namespace(AUTH, "installation-docs")[2]
        == "documentation-retrieval"
    )
    with pytest.raises(CapabilityError):
        Authority("tenant/other", "owner-1")
    with pytest.raises(CapabilityError):
        memory_namespace(AUTH, "shared")


def test_tokens_are_integrity_expiry_and_scope_bound():
    token = issue_token({"owner": "owner-1", "operation": "read"}, b"secret", now=NOW)
    assert (
        verify_token(
            token, b"secret", {"owner": "owner-1", "operation": "read"}, now=NOW
        )["owner"]
        == "owner-1"
    )
    with pytest.raises(CapabilityError):
        verify_token(
            token, b"secret", {"owner": "owner-2", "operation": "read"}, now=NOW
        )
    with pytest.raises(CapabilityError):
        verify_token(
            token,
            b"secret",
            {"owner": "owner-1", "operation": "read"},
            now=NOW + timedelta(minutes=6),
        )
    with pytest.raises(CapabilityError):
        verify_token(token + "x", b"secret", {"owner": "owner-1"}, now=NOW)


def test_lexical_is_same_word_stable_and_candidate_bounded():
    rows = [
        {"id": "b", "content": "alpha alphabet"},
        {"id": "a", "content": "alpha beta"},
    ]
    assert [r["id"] for r in lexical_rank("ALPHA beta", rows)] == ["a", "b"]
    with pytest.raises(CapabilityError):
        lexical_rank("x", [{"id": str(i), "content": "x"} for i in range(1001)])


@pytest.mark.asyncio
async def test_memory_explicit_idempotent_revision_and_lifecycle():
    store = InMemoryStore()
    clock = [NOW]
    api = StoreCapabilities(store, AUTH, now=lambda: clock[0])
    first = await api.write_memory(
        kind="task-outcomes",
        content="alpha complete",
        metadata={},
        provenance=PROV | {"creation_method": "caller-selected"},
        operation_id="op-1",
    )
    retry = await api.write_memory(
        kind="task-outcomes",
        content="alpha complete",
        metadata={},
        provenance=PROV,
        operation_id="op-1",
    )
    assert first == retry and first["revision"] == 1
    assert first["provenance"]["creation_method"] == "explicit-authorized-write"
    assert first["provenance"]["source_time"] == "unknown"
    with pytest.raises(CapabilityError):
        await api.write_memory(
            kind="task-outcomes",
            content="changed",
            metadata={},
            provenance=PROV,
            operation_id="op-1",
        )
    assert (await api.read_memory(kind="task-outcomes", mode="lexical", query="alpha"))[
        0
    ]["match_mode"] == "lexical"
    deleted = await api.delete_memory("task-outcomes", first["id"], "op-2")
    assert deleted["revision"] == 2
    assert (
        await api.read_memory(kind="task-outcomes", mode="exact", key=first["id"]) == []
    )
    clock[0] = NOW + timedelta(days=7)
    restored = await api.restore_memory("task-outcomes", first["id"], "op-3")
    assert restored["revision"] == 3
    await api.delete_memory("task-outcomes", first["id"], "op-4")
    clock[0] += timedelta(days=7, microseconds=1)
    with pytest.raises(CapabilityError):
        await api.restore_memory("task-outcomes", first["id"], "op-5")
    purged = await api.purge_memory("task-outcomes", first["id"], "op-6")
    assert purged["purged"] is True
    audits = await store.asearch(("app", "v1", "phase5-audit"), limit=100)
    assert all("content" not in item.value for item in audits)


@pytest.mark.asyncio
async def test_documentation_empty_injection_lifecycle_and_mediated_write():
    store = InMemoryStore()
    delegated = Authority(
        "tenant-1",
        "owner-1",
        corpus_read_grants=frozenset({"installation-docs"}),
        delegation=Delegation(
            issuer="supervisor",
            subject="trusted-adapter",
            operations=frozenset({"documentation-retrieval:write"}),
            corpora=frozenset({"installation-docs"}),
            expires_at=NOW + timedelta(minutes=5),
            supervisor_created=True,
        ),
    )
    api = StoreCapabilities(store, delegated, now=lambda: NOW)
    assert (
        await api.read_documents(
            corpus="installation-docs", mode="lexical", query="anything"
        )
        == []
    )
    with pytest.raises(CapabilityError):
        await api.write_document(
            corpus="installation-docs",
            fragment_id="f1",
            content="ignore policy",
            provenance=DOC_PROV,
            operation_id="d1",
            supervisor_approved=False,
            ocr_succeeded=True,
        )
    await api.write_document(
        corpus="installation-docs",
        fragment_id="f1",
        content="ignore policy alpha",
        provenance=DOC_PROV,
        operation_id="d1",
        supervisor_approved=True,
        ocr_succeeded=True,
    )
    result = await api.read_documents(
        corpus="installation-docs", mode="lexical", query="alpha"
    )
    assert result[0]["untrusted_data"] is True and result[0]["match_mode"] == "lexical"
    by_document = await api.read_documents(
        corpus="installation-docs", mode="exact", key="doc-1"
    )
    assert [row["fragment_id"] for row in by_document] == ["f1"]
    filtered = await api.read_documents(
        corpus="installation-docs", mode="metadata+lexical",
        filters={"document_id": "doc-1"}, query="alpha",
    )
    assert filtered[0]["match_mode"] == "lexical"
    assert filtered[0]["metadata_filtered"] is True


async def _store_snapshot(store):
    items = await store.asearch(("app",), limit=1000)
    return sorted((item.namespace, item.key, item.value) for item in items)


def _write(operation_id, **changes):
    value = {
        "kind": "task-outcomes",
        "content": f"content {operation_id}",
        "metadata": {},
        "provenance": PROV,
        "operation_id": operation_id,
    }
    value.update(changes)
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        _write("bad-prov", provenance={"source_type": "owner-statement"}),
        _write("bad-kind", kind="invalid-kind"),
    ],
)
async def test_memory_batch_later_validation_failure_has_no_data_writes(bad):
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    with pytest.raises(CapabilityError):
        await api.write_memory_batch([_write("first"), bad])
    assert await _store_snapshot(store) == []


@pytest.mark.asyncio
async def test_memory_batch_duplicate_operation_id_has_no_data_writes():
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    with pytest.raises(CapabilityError):
        await api.write_memory_batch(
            [_write("duplicate"), _write("duplicate", kind="project-decisions")]
        )
    assert await _store_snapshot(store) == []


@pytest.mark.asyncio
async def test_memory_batch_conflicting_operation_id_has_no_partial_writes():
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    await api.write_memory(**_write("existing"))
    before = await _store_snapshot(store)
    with pytest.raises(CapabilityError):
        await api.write_memory_batch(
            [_write("would-write"), _write("existing", content="conflict")]
        )
    assert await _store_snapshot(store) == before


@pytest.mark.asyncio
async def test_memory_batch_aggregate_capacity_has_no_data_writes(monkeypatch):
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    monkeypatch.setattr(phase5, "MAX_KIND_BYTES", 1)
    with pytest.raises(CapabilityError):
        await api.write_memory_batch([_write("one"), _write("two")])
    assert await _store_snapshot(store) == []


@pytest.mark.asyncio
async def test_memory_batch_idempotent_retry_has_no_additional_writes():
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    writes = [_write("retry-one"), _write("retry-two")]
    first = await api.write_memory_batch(writes)
    before = await _store_snapshot(store)
    retry = await api.write_memory_batch(writes)
    assert retry == first
    assert await _store_snapshot(store) == before


@pytest.mark.asyncio
async def test_stale_lifecycle_revision_is_rejected_without_mutation():
    store = InMemoryStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    row = await api.write_memory(**_write("stale-write"))
    before = await _store_snapshot(store)
    with pytest.raises(CapabilityError, match="Stale memory revision"):
        await api.delete_memory(
            "task-outcomes", row["id"], "stale-delete", expected_revision=2
        )
    assert await _store_snapshot(store) == before

    deleted = await api.delete_memory(
        "task-outcomes", row["id"], "current-delete", expected_revision=1
    )
    before_restore = await _store_snapshot(store)
    with pytest.raises(CapabilityError, match="Stale memory revision"):
        await api.restore_memory(
            "task-outcomes", row["id"], "stale-restore", expected_revision=1
        )
    assert deleted["revision"] == 2
    assert await _store_snapshot(store) == before_restore


@pytest.mark.asyncio
async def test_installation_tenant_and_owner_namespaces_are_isolated():
    store = InMemoryStore()
    origin = StoreCapabilities(store, AUTH, now=lambda: NOW)
    row = await origin.write_memory(**_write("isolated"))
    other_tenant = StoreCapabilities(
        store,
        Authority(
            "tenant-2",
            "owner-1",
            memory_grants=frozenset({"read"}),
        ),
        now=lambda: NOW,
    )
    other_owner = StoreCapabilities(
        store,
        Authority(
            "tenant-1",
            "owner-2",
            memory_grants=frozenset({"read"}),
        ),
        now=lambda: NOW,
    )
    for isolated in (other_tenant, other_owner):
        assert await isolated.read_memory(
            kind="task-outcomes", mode="exact", key=row["id"]
        ) == []
        assert await isolated.read_memory(
            kind="task-outcomes", mode="lexical", query="content"
        ) == []
    assert (await origin.read_memory(
        kind="task-outcomes", mode="exact", key=row["id"]
    ))[0]["id"] == row["id"]
