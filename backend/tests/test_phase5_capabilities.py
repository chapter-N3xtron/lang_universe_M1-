"""Synthetic, one-dimension-at-a-time Phase 5 contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from langgraph.store.base import SearchItem
from langgraph.store.memory import InMemoryStore

import src.phase5_capabilities as phase5
from src.phase5_capabilities import (
    Authority,
    CapabilityError,
    Delegation,
    StoreCapabilities,
    documentation_namespace,
    lexical_rank,
    memory_namespace,
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


@pytest.fixture(autouse=True)
def _enable_test_store_ttl(monkeypatch):
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


DOC_PROV = {
    "document_id": "doc-1",
    "locator": "p1",
    "title": "Guide",
    "source_revision": "r1",
    "digest": "abc",
    "source_status": "active",
    "source_type": "owner-upload",
}


def test_namespace_encoders_fix_every_scope_dimension():
    assert memory_namespace(AUTH, "task outcomes") == (
        "app",
        "v1",
        "cross-session-memory",
        "tenant:tenant-1",
        "trust:local-installation-v1",
        "owner:person:owner-1",
        "kind:task-outcomes",
    )
    assert (
        frozenset(
            {
                "user preferences",
                "user-provided facts",
                "project decisions",
                "task outcomes",
                "reusable instructions",
            }
        )
        == phase5.MEMORY_KINDS
    )
    for kind in phase5.MEMORY_KINDS:
        assert memory_namespace(AUTH, kind)[-1] == f"kind:{kind.replace(' ', '-')}"
    for former_kind in (
        "user-preferences",
        "user-provided-facts",
        "project-decisions",
        "task-outcomes",
        "reusable-instructions",
    ):
        with pytest.raises(CapabilityError, match="Unsupported memory kind"):
            memory_namespace(AUTH, former_kind)
    assert documentation_namespace(AUTH, "installation-docs") == (
        "app",
        "v1",
        "documentation-retrieval",
        "tenant:tenant-1",
        "trust:local-installation-v1",
        "owner:person:owner-1",
        "corpus:installation-docs",
        "record:fragment",
    )
    with pytest.raises(CapabilityError):
        Authority("tenant/other", "owner-1")
    with pytest.raises(CapabilityError):
        memory_namespace(AUTH, "shared")
    for record_type in ("head", "operation", "session"):
        with pytest.raises(CapabilityError):
            documentation_namespace(AUTH, "installation-docs", record_type)


@pytest.mark.asyncio
async def test_prefix_searches_fix_every_namespace_dimension_before_result_filtering():
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.searches = []

        async def asearch(self, namespace_prefix, **kwargs):
            self.searches.append((namespace_prefix, kwargs))
            return await super().asearch(namespace_prefix, **kwargs)

    store = RecordingStore()
    memory_ns = memory_namespace(AUTH, "task outcomes")
    memory_record = {
        "record_type": "memory",
        "id": "authorized-memory",
        "content": "authorized needle",
        "provenance": {"source_type": "session", "source_id": "allowed"},
        "lifecycle_state": "active",
    }
    await store.aput(memory_ns, "authorized-memory", memory_record, index=False)
    for index, replacement in [
        (2, "documentation-retrieval"),
        (3, "tenant:other"),
        (4, "trust:other"),
        (5, "owner:work:owner-1"),
        (5, "owner:person:other"),
        (6, "kind:project-decisions"),
    ]:
        sibling = list(memory_ns)
        sibling[index] = replacement
        await store.aput(
            tuple(sibling),
            f"sibling-{index}-{replacement}",
            memory_record
            | {
                "id": f"sibling-{index}-{replacement}",
            },
            index=False,
        )

    memory = await StoreCapabilities(store, AUTH, now=lambda: NOW).read_memory(
        kind="task outcomes", mode="lexical", query="needle"
    )
    assert [row["id"] for row in memory] == ["authorized-memory"]

    document_ns = documentation_namespace(AUTH, "installation-docs")
    canonical_ns = documentation_namespace(AUTH, "installation-docs", "document")
    document_record = {
        "record_type": "fragment",
        "id": "authorized-document",
        "document_id": "doc-authorized",
        "content": "authorized manual",
        "corpus_revision": "1",
    }
    await store.aput(document_ns, "authorized-document", document_record, index=False)
    await store.aput(
        canonical_ns,
        "doc-authorized",
        {
            "record_type": "document",
            "id": "doc-authorized",
            "source_status": "active",
            "corpus_revision": "1",
            "tags": [],
        },
        index=False,
    )
    for index, replacement in [
        (2, "cross-session-memory"),
        (3, "tenant:other"),
        (4, "trust:other"),
        (5, "owner:work:owner-1"),
        (5, "owner:person:other"),
        (6, "corpus:other-docs"),
        (7, "record:operation"),
    ]:
        sibling = list(document_ns)
        sibling[index] = replacement
        await store.aput(
            tuple(sibling),
            f"sibling-{index}-{replacement}",
            document_record
            | {
                "id": f"sibling-{index}-{replacement}",
            },
            index=False,
        )

    documents = await StoreCapabilities(store, AUTH, now=lambda: NOW).read_documents(
        corpus="installation-docs", mode="semantic", query="manual"
    )
    assert [row["id"] for row in documents] == ["authorized-document"]
    assert store.searches == [
        (memory_ns, {"limit": phase5.MAX_CANDIDATES, "offset": 0}),
        (
            document_ns,
            {
                "query": "manual",
                "limit": phase5.MAX_CANDIDATES,
                "offset": 0,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_scope_and_request_rejections_happen_before_any_store_access():
    class NoAccessStore(InMemoryStore):
        calls = 0

        async def aget(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("rejected request touched Store.get")

        async def asearch(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("rejected request touched Store.search")

    store = NoAccessStore()
    api = StoreCapabilities(store, AUTH)
    requests = [
        api.read_memory(
            kind="task outcomes", mode="metadata", filters={"owner_id": "other"}
        ),
        api.read_memory(
            kind="task outcomes",
            mode="lexical",
            query="x" * (phase5.MAX_QUERY_BYTES + 1),
        ),
        api.read_memory(kind=("task outcomes", "project decisions"), mode="lexical"),
        api.read_documents(
            corpus="installation-docs", mode="metadata", filters={"tenant_id": "other"}
        ),
        api.read_documents(
            corpus="installation-docs",
            mode="semantic",
            query="x" * (phase5.MAX_QUERY_BYTES + 1),
        ),
        api.read_documents(corpus=["installation-docs", "other-docs"], mode="semantic"),
    ]
    for request in requests:
        with pytest.raises(CapabilityError):
            await request

    unauthorized = StoreCapabilities(
        store,
        Authority("tenant-1", "owner-1", memory_grants=frozenset({"read"})),
    )
    with pytest.raises(CapabilityError, match="Capability denied"):
        await unauthorized.read_documents(
            corpus="installation-docs", mode="exact", key="known-or-missing"
        )
    assert store.calls == 0


@pytest.mark.asyncio
async def test_metadata_filtering_is_result_filtering_after_authorized_prefix_search():
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.searches = []

        async def asearch(self, namespace_prefix, **kwargs):
            self.searches.append((namespace_prefix, kwargs))
            return await super().asearch(namespace_prefix, **kwargs)

    store = RecordingStore()
    namespace = memory_namespace(AUTH, "task outcomes")
    for memory_id, source_id in (("one", "selected"), ("two", "other")):
        await store.aput(
            namespace,
            memory_id,
            {
                "record_type": "memory",
                "id": memory_id,
                "content": "same authorized content",
                "provenance": {"source_type": "session", "source_id": source_id},
                "lifecycle_state": "active",
            },
            index=False,
        )

    result = await StoreCapabilities(store, AUTH, now=lambda: NOW).read_memory(
        kind="task outcomes", mode="metadata", filters={"source_id": "selected"}
    )
    assert [row["id"] for row in result] == ["one"]
    assert store.searches == [
        (namespace, {"limit": phase5.MAX_CANDIDATES, "offset": 0})
    ]


@pytest.mark.parametrize("principal", ["jasper", "coder", "librarian"])
def test_specialist_grants_are_independent_and_corpus_delegation_is_explicit(principal):
    authority = Authority.from_verified_context(
        tenant_id="tenant-1",
        owner_id="owner-1",
        principal_id=principal,
        server_verified=True,
        delegated_memory=frozenset({"read"}),
        delegated_corpora=frozenset({"installation-docs"}),
    )
    assert authority.memory_grants == frozenset({"read"})
    assert authority.corpus_read_grants == frozenset({"installation-docs"})


def test_ocr_denies_memory_but_accepts_explicit_documentation_delegation():
    with pytest.raises(CapabilityError, match="OCR cannot receive memory grants"):
        Authority.from_verified_context(
            tenant_id="tenant-1",
            owner_id="owner-1",
            principal_id="ocr",
            server_verified=True,
            delegated_memory=frozenset({"read"}),
        )
    authority = Authority.from_verified_context(
        tenant_id="tenant-1",
        owner_id="owner-1",
        principal_id="ocr",
        server_verified=True,
        delegated_corpora=frozenset({"installation-docs"}),
    )
    assert authority.memory_grants == frozenset()
    assert authority.corpus_read_grants == frozenset({"installation-docs"})


@pytest.mark.parametrize(
    "changes",
    [
        {"owner_type": "work"},
        {"trust_domain": "shared"},
    ],
)
def test_shared_and_work_authority_scope_is_rejected(changes):
    with pytest.raises(CapabilityError, match="Unsupported authority"):
        Authority("tenant-1", "owner-1", **changes)


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
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.puts = []

        async def aput(self, namespace, key, value, *, index=None, ttl=None):
            self.puts.append((namespace, key, ttl))
            return await super().aput(namespace, key, value, index=index, ttl=ttl)

    store = RecordingStore()
    clock = [NOW]
    api = StoreCapabilities(store, AUTH, now=lambda: clock[0])
    first = await api.write_memory(
        kind="task outcomes",
        content="alpha complete",
        metadata={},
        provenance=PROV | {"creation_method": "caller-selected"},
        operation_id="op-1",
    )
    retry = await api.write_memory(
        kind="task outcomes",
        content="alpha complete",
        metadata={},
        provenance=PROV,
        operation_id="op-1",
    )
    assert first == retry and first["revision"] == 1
    memory_ns = memory_namespace(AUTH, "task outcomes")
    items = await store.asearch(memory_ns, limit=100)
    assert [(item.namespace, item.key) for item in items] == [(memory_ns, first["id"])]
    assert not any(
        "record:revision" in namespace or "record:operation" in namespace
        for namespace, _, _ in store.puts
    )
    assert first["provenance"]["creation_method"] == "explicit-authorized-write"
    assert first["provenance"]["source_time"] == "unknown"
    with pytest.raises(CapabilityError):
        await api.write_memory(
            kind="task outcomes",
            content="changed",
            metadata={},
            provenance=PROV,
            operation_id="op-1",
        )
    assert (await api.read_memory(kind="task outcomes", mode="lexical", query="alpha"))[
        0
    ]["match_mode"] == "lexical"
    deleted = await api.delete_memory("task outcomes", first["id"], "op-2")
    assert deleted["revision"] == 2
    assert store.puts[-2] == (memory_ns, first["id"], phase5.DELETED_MEMORY_TTL_MINUTES)
    assert (
        await api.read_memory(kind="task outcomes", mode="exact", key=first["id"]) == []
    )
    clock[0] = NOW + timedelta(days=7)
    restored = await api.restore_memory("task outcomes", first["id"], "op-3")
    assert restored["revision"] == 3
    assert store.puts[-2] == (memory_ns, first["id"], None)
    await api.delete_memory("task outcomes", first["id"], "op-4")
    clock[0] += timedelta(days=7, microseconds=1)
    with pytest.raises(CapabilityError):
        await api.restore_memory("task outcomes", first["id"], "op-5")
    purged = await api.purge_memory("task outcomes", first["id"], "op-6")
    assert purged["purged"] is True
    assert await store.aget(memory_ns, first["id"]) is None
    audits = await store.asearch(("app", "v1", "phase5-audit"), limit=100)
    assert all("content" not in item.value for item in audits)
    assert all("trust:local-installation-v1" in item.namespace for item in audits)


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
            corpus="installation-docs", mode="semantic", query="anything"
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
        corpus="installation-docs", mode="semantic", query="alpha"
    )
    assert result[0]["untrusted_data"] is True and result[0]["match_mode"] == "semantic"
    by_document = await api.read_documents(
        corpus="installation-docs",
        mode="exact",
        key="doc-1",
        record_type="document",
    )
    assert [row["id"] for row in by_document] == ["doc-1"]
    assert "content" not in by_document[0]
    semantic = await api.read_documents(
        corpus="installation-docs",
        mode="semantic",
        query="alpha",
    )
    assert semantic[0]["match_mode"] == "semantic"
    assert semantic[0]["metadata_filtered"] is False


@pytest.mark.asyncio
async def test_canonical_document_and_fragment_are_single_direct_key_records():
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
    result = await api.write_document(
        corpus="installation-docs",
        fragment_id="fragment-1",
        content="canonical body",
        provenance=DOC_PROV,
        operation_id="canonical-write",
        supervisor_approved=True,
        ocr_succeeded=True,
        tags=["  Reference  ", "REFERENCE", "API Guide"],
    )
    retry = await api.write_document(
        corpus="installation-docs",
        fragment_id="fragment-1",
        content="canonical body",
        provenance=DOC_PROV,
        operation_id="canonical-write",
        supervisor_approved=True,
        ocr_succeeded=True,
        tags=["api guide", "reference"],
    )
    assert retry == result
    second = await api.write_document(
        corpus="installation-docs",
        fragment_id="fragment-2",
        content="second bounded fragment",
        provenance=DOC_PROV
        | {
            "locator": "p2",
            "digest": "fragment-two-digest",
            "document_digest": "abc",
        },
        operation_id="canonical-write-2",
        supervisor_approved=True,
        ocr_succeeded=True,
        tags=["api guide", "reference"],
    )
    assert second["document_id"] == "doc-1"

    document_ns = documentation_namespace(AUTH, "installation-docs", "document")
    fragment_ns = documentation_namespace(AUTH, "installation-docs", "fragment")
    documents = await store.asearch(document_ns, limit=1000)
    fragments = await store.asearch(fragment_ns, limit=1000)
    assert [(item.key, item.value["tags"]) for item in documents] == [
        ("doc-1", ["api guide", "reference"])
    ]
    assert "content" not in documents[0].value
    assert sorted((item.key, item.value["content"]) for item in fragments) == [
        ("fragment-1", "canonical body"),
        ("fragment-2", "second bounded fragment"),
    ]
    assert "tags" not in fragments[0].value and "title" not in fragments[0].value
    all_documentation = await store.asearch(
        ("app", "v1", "documentation-retrieval"), limit=1000
    )
    assert {item.namespace[-1] for item in all_documentation} == {
        "record:document",
        "record:fragment",
    }


@pytest.mark.asyncio
async def test_document_semantic_search_delegates_query_index_and_ranking_to_store(
    monkeypatch,
):
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.puts = []
            self.semantic_searches = []

        async def aput(self, namespace, key, value, *, index=None, ttl=None):
            self.puts.append((namespace, key, index))
            return await super().aput(namespace, key, value, index=index, ttl=ttl)

        async def asearch(self, namespace_prefix, **kwargs):
            if kwargs.get("query") is None:
                return await super().asearch(namespace_prefix, **kwargs)
            self.semantic_searches.append((namespace_prefix, kwargs))
            items = await super().asearch(
                namespace_prefix,
                limit=kwargs["limit"],
                offset=kwargs["offset"],
            )
            by_key = {item.key: item for item in items}
            return [
                SearchItem(
                    namespace=tuple(by_key[key].namespace),
                    key=key,
                    value=by_key[key].value,
                    created_at=by_key[key].created_at,
                    updated_at=by_key[key].updated_at,
                    score=score,
                )
                for key, score in (("fragment-low", 0.2), ("fragment-high", 0.9))
            ]

    store = RecordingStore()
    writer_authority = Authority(
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
    api = StoreCapabilities(store, writer_authority, now=lambda: NOW)
    for fragment_id, document_id, tag in (
        ("fragment-high", "doc-high", "reference"),
        ("fragment-low", "doc-low", "guide"),
    ):
        await api.write_document(
            corpus="installation-docs",
            fragment_id=fragment_id,
            content=f"content for {document_id}",
            provenance=DOC_PROV
            | {
                "document_id": document_id,
                "digest": f"digest-{document_id}",
            },
            operation_id=f"write-{document_id}",
            supervisor_approved=True,
            ocr_succeeded=True,
            tags=[tag],
        )

    document_ns = documentation_namespace(AUTH, "installation-docs", "document")
    fragment_ns = documentation_namespace(AUTH, "installation-docs", "fragment")
    document_puts = [put for put in store.puts if put[0] == document_ns]
    fragment_puts = [put for put in store.puts if put[0] == fragment_ns]
    assert all(index is False for _, _, index in document_puts)
    assert all(index == ["content"] for _, _, index in fragment_puts)

    def handcrafted_rank_must_not_run(*_args, **_kwargs):
        raise AssertionError("document semantic search called lexical_rank")

    monkeypatch.setattr(phase5, "lexical_rank", handcrafted_rank_must_not_run)
    reader = StoreCapabilities(store, AUTH, now=lambda: NOW)
    results = await reader.read_documents(
        corpus="installation-docs", mode="semantic", query="conceptual request"
    )
    assert store.semantic_searches == [
        (
            fragment_ns,
            {
                "query": "conceptual request",
                "limit": phase5.MAX_CANDIDATES,
                "offset": 0,
            },
        )
    ]
    assert [(row["id"], row["score"]) for row in results] == [
        ("fragment-low", 0.2),
        ("fragment-high", 0.9),
    ]
    assert all(row["match_mode"] == "semantic" for row in results)

    exact = await reader.read_documents(
        corpus="installation-docs", mode="exact", key="fragment-high"
    )
    tagged = await reader.read_documents(
        corpus="installation-docs", mode="metadata", filters={"tag": "guide"}
    )
    assert exact[0]["id"] == "fragment-high"
    assert [row["id"] for row in tagged] == ["doc-low"]
    assert "tags" not in (await store.aget(fragment_ns, "fragment-low")).value


@pytest.mark.asyncio
async def test_exact_document_and_fragment_reads_use_aget_without_enumeration():
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.gets = []
            self.searches = []

        async def aget(self, namespace, key):
            self.gets.append((namespace, key))
            return await super().aget(namespace, key)

        async def asearch(self, namespace_prefix, **kwargs):
            self.searches.append((namespace_prefix, kwargs))
            return await super().asearch(namespace_prefix, **kwargs)

    store = RecordingStore()
    document_ns = documentation_namespace(AUTH, "installation-docs", "document")
    fragment_ns = documentation_namespace(AUTH, "installation-docs", "fragment")
    await store.aput(
        document_ns,
        "doc-exact",
        {
            "record_type": "document",
            "id": "doc-exact",
            "source_status": "active",
            "corpus_revision": "1",
            "tags": [],
        },
        index=False,
    )
    await store.aput(
        fragment_ns,
        "fragment-exact",
        {
            "record_type": "fragment",
            "id": "fragment-exact",
            "fragment_id": "fragment-exact",
            "document_id": "doc-exact",
            "content": "exact body",
            "corpus_revision": "1",
        },
        index=False,
    )
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    document = await api.read_documents(
        corpus="installation-docs",
        mode="exact",
        key="doc-exact",
        record_type="document",
    )
    assert document[0]["id"] == "doc-exact"
    assert store.gets == [(document_ns, "doc-exact")]
    assert store.searches == []

    store.gets.clear()
    fragment = await api.read_documents(
        corpus="installation-docs", mode="exact", key="fragment-exact"
    )
    assert fragment[0]["id"] == "fragment-exact"
    assert store.gets == [
        (fragment_ns, "fragment-exact"),
        (document_ns, "doc-exact"),
    ]
    assert store.searches == []


@pytest.mark.asyncio
async def test_document_tag_and_fixed_corpus_bounds_fail_before_mutation():
    store = InMemoryStore()
    api = StoreCapabilities(
        store,
        Authority(
            "tenant-1",
            "owner-1",
            corpus_read_grants=frozenset({"installation-docs"}),
            delegation=Delegation(
                "supervisor",
                "adapter",
                frozenset({"documentation-retrieval:write"}),
                frozenset({"installation-docs"}),
                NOW + timedelta(minutes=1),
                True,
            ),
        ),
        now=lambda: NOW,
    )
    with pytest.raises(CapabilityError, match="document tags"):
        await api.write_document(
            corpus="installation-docs",
            fragment_id="bounded-fragment",
            content="body",
            provenance=DOC_PROV,
            operation_id="bounded-write",
            supervisor_approved=True,
            ocr_succeeded=True,
            tags=[f"tag-{index}" for index in range(phase5.MAX_DOCUMENT_TAGS + 1)],
        )
    with pytest.raises(CapabilityError, match="Capability denied"):
        await api.read_documents(corpus="other-docs", mode="semantic", query="body")
    assert not await store.asearch(("app", "v1", "documentation-retrieval"))


async def _store_snapshot(store):
    items = await store.asearch(("app",), limit=1000)
    return sorted((item.namespace, item.key, item.value) for item in items)


def _write(operation_id, **changes):
    value = {
        "kind": "task outcomes",
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
            [_write("duplicate"), _write("duplicate", kind="project decisions")]
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
async def test_capacity_pages_past_1000_without_expanding_retrieval_candidates():
    class RecordingStore(InMemoryStore):
        def __init__(self):
            super().__init__()
            self.puts = []
            self.searches = []

        async def aput(self, namespace, key, value, *, index=None, ttl=None):
            self.puts.append((namespace, key))
            return await super().aput(namespace, key, value, index=index, ttl=ttl)

        async def asearch(self, namespace_prefix, **kwargs):
            self.searches.append((namespace_prefix, kwargs))
            return await super().asearch(namespace_prefix, **kwargs)

    store = RecordingStore()
    api = StoreCapabilities(store, AUTH, now=lambda: NOW)
    proposed = await api._validated_write_plan(
        kind="task outcomes",
        content="proposal",
        metadata={},
        provenance=PROV,
        operation_id="over-pages",
        content_class="ordinary",
        timestamp=NOW.isoformat(),
    )
    target_size = 15_700
    proposed_size = len(phase5._canonical(proposed.envelope))
    assert target_size * 1000 + proposed_size <= phase5.MAX_KIND_BYTES
    assert target_size * 1002 + proposed_size > phase5.MAX_KIND_BYTES

    namespace = memory_namespace(AUTH, "task outcomes")
    for index in range(1002):
        identifier = f"{index:064x}"
        envelope = proposed.envelope | {
            "id": identifier,
            "content": "needle ",
            "operation_id": f"seed-{index}",
            "request_digest": identifier,
        }
        padding = target_size - len(phase5._canonical(envelope))
        envelope["content"] += "x" * padding
        assert len(phase5._canonical(envelope)) == target_size
        await store.aput(namespace, identifier, envelope, index=False)

    store.puts.clear()
    store.searches.clear()
    with pytest.raises(CapabilityError, match="capacity exceeded"):
        await api.write_memory(**_write("over-pages", content="proposal"))
    assert store.puts == []
    assert store.searches == [
        (namespace, {"limit": 1000, "offset": 0}),
        (namespace, {"limit": 1000, "offset": 1000}),
    ]

    store.searches.clear()
    result = await api.read_memory(
        kind="task outcomes", mode="lexical", query="needle", limit=10
    )
    assert len(result) == 10
    assert store.searches == [
        (namespace, {"limit": phase5.MAX_CANDIDATES, "offset": 0})
    ]


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
            "task outcomes", row["id"], "stale-delete", expected_revision=2
        )
    assert await _store_snapshot(store) == before

    deleted = await api.delete_memory(
        "task outcomes", row["id"], "current-delete", expected_revision=1
    )
    before_restore = await _store_snapshot(store)
    with pytest.raises(CapabilityError, match="Stale memory revision"):
        await api.restore_memory(
            "task outcomes", row["id"], "stale-restore", expected_revision=1
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
        assert (
            await isolated.read_memory(
                kind="task outcomes", mode="exact", key=row["id"]
            )
            == []
        )
        assert (
            await isolated.read_memory(
                kind="task outcomes", mode="lexical", query="content"
            )
            == []
        )
    assert (
        await origin.read_memory(kind="task outcomes", mode="exact", key=row["id"])
    )[0]["id"] == row["id"]
