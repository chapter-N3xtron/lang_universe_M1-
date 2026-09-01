"""Focused graph contracts for Phase 5 current-thread document-link mutations."""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from src import chat_ui
from src.phase5_capabilities import Authority, documentation_namespace


class SyntheticOwner:
    def __init__(self, identity: str = "owner-1", authenticated: bool = True):
        self.identity = identity
        self.is_authenticated = authenticated
        self.display_name = "Synthetic Owner"
        self.permissions: list[str] = []


class TrackingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.gets: list[tuple[tuple[str, ...], str]] = []
        self.searches: list[tuple[str, ...]] = []
        self.puts: list[tuple[tuple[str, ...], str]] = []
        self.deletes: list[tuple[tuple[str, ...], str]] = []

    async def aget(self, namespace: tuple[str, ...], key: str):
        self.gets.append((namespace, key))
        return await super().aget(namespace, key)

    async def asearch(self, namespace_prefix: tuple[str, ...], **kwargs: Any):
        self.searches.append(namespace_prefix)
        return await super().asearch(namespace_prefix, **kwargs)

    async def aput(
        self, namespace: tuple[str, ...], key: str, value: dict, **kwargs: Any
    ):
        self.puts.append((namespace, key))
        await super().aput(namespace, key, value, **kwargs)

    async def adelete(self, namespace: tuple[str, ...], key: str):
        self.deletes.append((namespace, key))
        await super().adelete(namespace, key)


class UnavailableStore(TrackingStore):
    async def aget(self, namespace: tuple[str, ...], key: str):
        self.gets.append((namespace, key))
        raise RuntimeError("synthetic backend detail")


@pytest.fixture(autouse=True)
def installation(monkeypatch):
    monkeypatch.setenv("INSTALLATION_TENANT_ID", "tenant-1")
    monkeypatch.setenv("INSTALLATION_OWNER_ID", "owner-1")
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)

    def no_model():
        raise AssertionError("document-link mutation must not invoke a model")

    monkeypatch.setattr(chat_ui, "get_llm", no_model)


def config(thread_id: str, user: SyntheticOwner | None = None) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "assistant_id": "assistant-1",
            "graph_id": "chat_ui",
            "langgraph_auth_user": user or SyntheticOwner(),
        }
    }


def request(action: str, document_id: str, **extra: Any) -> dict:
    return {
        "session_document_link_action": {
            "action": action,
            "document_id": document_id,
            **extra,
        }
    }


def graph(store: InMemoryStore):
    return chat_ui.create_chat_ui().compile(
        checkpointer=InMemorySaver(),
        store=store,
    )


def document_namespace() -> tuple[str, ...]:
    return documentation_namespace(
        Authority("tenant-1", "owner-1"), "installation-docs", "document"
    )


def seed_document(
    store: InMemoryStore, document_id: str, status: str = "active"
) -> None:
    store.put(
        document_namespace(),
        document_id,
        {
            "schema_version": 1,
            "record_type": "document",
            "id": document_id,
            "source_status": status,
            "title": "Canonical title",
            "tags": ["canonical-tag"],
        },
        index=False,
    )


FAILURE = {"ok": False, "status": "denied", "error": "link_mutation_failed"}


@pytest.mark.asyncio
async def test_owner_add_is_bound_to_current_thread_and_uses_exact_canonical_get():
    store = TrackingStore()
    seed_document(store, "doc-1")
    canonical_before = store.get(document_namespace(), "doc-1").value
    app = graph(store)

    result = await app.ainvoke(
        request("add", "doc-1") | {"thread_identity": "forged-other-thread"},
        config("thread-current"),
    )

    assert result["session_document_ids"] == ["doc-1"]
    assert result["session_document_link_action"] == {}
    assert result["session_document_link_result"] == {
        "ok": True,
        "status": "complete",
        "action": "add",
        "changed": True,
    }
    assert (document_namespace(), "doc-1") in store.gets
    assert document_namespace() not in store.searches
    assert store.get(document_namespace(), "doc-1").value == canonical_before
    assert not store.deletes
    assert app.get_state(config("thread-other")).values == {}


@pytest.mark.asyncio
async def test_input_is_id_only_and_authorization_failures_do_not_change_links():
    store = TrackingStore()
    seed_document(store, "doc-1")
    app = graph(store)
    current = config("thread-current")
    await app.ainvoke(request("add", "doc-1"), current)

    forbidden = [
        "thread_id",
        "session_id",
        "owner",
        "tenant",
        "namespace",
        "content",
        "tags",
        "metadata",
    ]
    for field in forbidden:
        result = await app.ainvoke(
            request("remove", "doc-1", **{field: "forged"}), current
        )
        assert result["session_document_ids"] == ["doc-1"]
        assert result["session_document_link_result"] == FAILURE
        assert result["session_document_link_action"] == {}

    malformed = [
        {"action": "delete", "document_id": "doc-1"},
        {"action": "remove", "document_id": "bad/id"},
        "remove:doc-1",
    ]
    for payload in malformed:
        result = await app.ainvoke({"session_document_link_action": payload}, current)
        assert result["session_document_ids"] == ["doc-1"]
        assert result["session_document_link_result"] == FAILURE

    denied_configs = [
        config("thread-current", SyntheticOwner("not-owner")),
        config("thread-current", SyntheticOwner(authenticated=False)),
        config("thread-current"),
    ]
    denied_configs[-1]["configurable"].pop("langgraph_auth_user")
    for denied_config in denied_configs:
        denied = await app.ainvoke(request("remove", "doc-1"), denied_config)
        assert denied["session_document_ids"] == ["doc-1"]
        assert denied["session_document_link_result"] == FAILURE


@pytest.mark.asyncio
async def test_add_remove_are_idempotent_and_remove_isolates_other_threads():
    store = TrackingStore()
    seed_document(store, "shared-doc")
    app = graph(store)
    first = config("thread-first")
    second = config("thread-second")

    await app.ainvoke(request("add", "shared-doc"), first)
    duplicate = await app.ainvoke(request("add", "shared-doc"), first)
    await app.ainvoke(request("add", "shared-doc"), second)
    removed = await app.ainvoke(request("remove", "shared-doc"), first)
    removed_again = await app.ainvoke(request("remove", "shared-doc"), first)

    assert duplicate["session_document_ids"] == ["shared-doc"]
    assert duplicate["session_document_link_result"]["changed"] is False
    assert removed["session_document_ids"] == []
    assert removed_again["session_document_ids"] == []
    assert removed_again["session_document_link_result"]["changed"] is False
    assert app.get_state(second).values["session_document_ids"] == ["shared-doc"]
    assert store.get(document_namespace(), "shared-doc") is not None


@pytest.mark.asyncio
async def test_add_at_100_rejects_without_eviction_or_partial_change():
    store = TrackingStore()
    seed_document(store, "doc-new")
    app = graph(store)
    current = config("thread-full")
    existing = [f"doc-{index}" for index in range(100)]

    result = await app.ainvoke(
        request("add", "doc-new") | {"session_document_ids": existing}, current
    )

    assert result["session_document_ids"] == existing
    assert result["session_document_link_result"] == FAILURE
    assert len(result["session_document_ids"]) == 100


@pytest.mark.asyncio
async def test_missing_inactive_and_unavailable_documents_share_sanitized_failure():
    store = TrackingStore()
    seed_document(store, "inactive-doc", "withdrawn")
    app = graph(store)

    missing = await app.ainvoke(request("add", "missing-doc"), config("missing"))
    inactive = await app.ainvoke(request("add", "inactive-doc"), config("inactive"))
    unavailable = await graph(UnavailableStore()).ainvoke(
        request("add", "unknown-doc"), config("unavailable")
    )

    for result in (missing, inactive, unavailable):
        assert result.get("session_document_ids", []) == []
        assert result["session_document_link_result"] == FAILURE
        assert result["session_document_link_action"] == {}


@pytest.mark.asyncio
async def test_no_action_preserves_existing_chat_routing(monkeypatch):
    class Response:
        content = "done"

    class Model:
        def invoke(self, _messages):
            return Response()

    monkeypatch.setattr(chat_ui, "get_llm", Model)
    called = False

    async def fake_jasper(state, config):
        nonlocal called
        called = True
        return {"messages": [{"role": "assistant", "content": "ordinary chat"}]}

    monkeypatch.setattr(chat_ui, "create_jasper_graph", lambda: fake_jasper)
    app = graph(TrackingStore())

    result = await app.ainvoke(
        {
            "messages": [{"role": "user", "content": "hello"}],
            "execution_mode": "autonomous",
            "target_agent": "jasper",
        },
        config("ordinary-chat"),
    )

    assert called is True
    assert result["messages"][-1]["content"] == "ordinary chat"
