"""Phase 5 task 7.8 source/graph verification gaps.

The broader Phase 5 suite already covers link authorization, bounds, idempotency,
reopen/many-thread checkpoint behavior, removal isolation, and Jasper exact-use linking.
These tests focus only on the previously uncombined Store-interface contract and an
executed graph proof that linked canonical content is not automatically injected.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import SearchItem
from langgraph.store.memory import InMemoryStore

from src import jasper_agent
from src.installation_auth import (
    authorize_store_get,
    authorize_store_search,
)
from src.phase5_capabilities import (
    MAX_CANDIDATES,
    Authority,
    StoreCapabilities,
    documentation_namespace,
)
from src.visual_models import JasperResponse

_ENV = {
    "INSTALLATION_TENANT_ID": "tenant-1",
    "INSTALLATION_OWNER_ID": "owner-1",
}
_AUTHORITY = Authority(
    "tenant-1",
    "owner-1",
    corpus_read_grants=frozenset({"installation-docs"}),
)


@pytest.fixture(autouse=True)
def _enable_test_store_ttl(monkeypatch):
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


class NativeSemanticStore(InMemoryStore):
    """Recording double whose query path supplies the Store's order and scores."""

    def __init__(self) -> None:
        super().__init__()
        self.semantic_calls: list[tuple[tuple[str, ...], dict]] = []

    async def asearch(self, namespace_prefix, **kwargs):
        if kwargs.get("query") is None:
            return await super().asearch(namespace_prefix, **kwargs)
        self.semantic_calls.append((namespace_prefix, dict(kwargs)))
        items = await super().asearch(
            namespace_prefix,
            limit=kwargs["limit"],
            offset=kwargs["offset"],
        )
        return [
            SearchItem(
                namespace=tuple(item.namespace),
                key=item.key,
                value=item.value,
                created_at=item.created_at,
                updated_at=item.updated_at,
                score=0.73,
            )
            for item in reversed(items)
        ]


def _context():
    return SimpleNamespace(
        user=SimpleNamespace(identity="owner-1", tenant_id="tenant-1")
    )


async def _seed_canonical_records(store: InMemoryStore, content: str) -> None:
    document_namespace = documentation_namespace(
        _AUTHORITY, "installation-docs", "document"
    )
    fragment_namespace = documentation_namespace(
        _AUTHORITY, "installation-docs", "fragment"
    )
    await store.aput(
        document_namespace,
        "doc-shared",
        {
            "record_type": "document",
            "id": "doc-shared",
            "corpus": "installation-docs",
            "source_status": "active",
            "tags": ["canonical", "shared"],
            "title": "Shared canonical document",
        },
        index=False,
    )
    await store.aput(
        fragment_namespace,
        "fragment-stable",
        {
            "record_type": "fragment",
            "id": "fragment-stable",
            "fragment_id": "fragment-stable",
            "document_id": "doc-shared",
            "content": content,
            "corpus": "installation-docs",
        },
        index=["content"],
    )


@pytest.mark.asyncio
async def test_manual_sdk_and_jasper_share_canonical_keys_tags_and_native_search():
    store = NativeSemanticStore()
    await _seed_canonical_records(store, "bounded semantic excerpt")
    document_namespace = documentation_namespace(
        _AUTHORITY, "installation-docs", "document"
    )
    fragment_namespace = documentation_namespace(
        _AUTHORITY, "installation-docs", "fragment"
    )

    manual_get = {"namespace": ("installation-docs", "documents"), "key": "doc-shared"}
    manual_search = {
        "namespace": ("installation-docs", "fragments"),
        "filter": None,
        "query": "semantic concept",
        "limit": 20,
        "offset": 0,
    }
    with patch.dict(os.environ, _ENV, clear=False):
        assert await authorize_store_get(_context(), manual_get) is False
        assert await authorize_store_search(_context(), manual_search) is False
    assert manual_get["namespace"] == ("installation-docs", "documents")
    assert manual_search["namespace"] == ("installation-docs", "fragments")

    jasper = StoreCapabilities(store, _AUTHORITY)
    jasper_document = await jasper.read_documents(
        corpus="installation-docs",
        mode="exact",
        key="doc-shared",
        record_type="document",
        limit=1,
    )
    jasper_fragments = await jasper.read_documents(
        corpus="installation-docs",
        mode="semantic",
        query="semantic concept",
        limit=20,
    )

    assert jasper_document[0]["tags"] == ["canonical", "shared"]
    assert [(item["id"], item["score"]) for item in jasper_fragments] == [
        ("fragment-stable", 0.73)
    ]
    assert store.semantic_calls[0][0] == fragment_namespace
    assert store.semantic_calls[0][1]["query"] == "semantic concept"
    assert store.semantic_calls[0][1]["limit"] == MAX_CANDIDATES
    assert store.semantic_calls[0][1]["offset"] == 0

    documents = await store.asearch(document_namespace, limit=1000)
    fragments = await store.asearch(fragment_namespace, limit=1000)
    assert [(item.key, item.value["tags"]) for item in documents] == [
        ("doc-shared", ["canonical", "shared"])
    ]
    assert [item.key for item in fragments] == ["fragment-stable"]
    assert "tags" not in fragments[0].value and "title" not in fragments[0].value


@pytest.mark.asyncio
async def test_unavailable_canonical_resolution_does_not_change_stable_reference():
    store = InMemoryStore()
    linked_ids = ["doc-unavailable"]
    manual_get = {
        "namespace": ("installation-docs", "documents"),
        "key": linked_ids[0],
    }
    with patch.dict(os.environ, _ENV, clear=False):
        assert await authorize_store_get(_context(), manual_get) is False

    assert await store.aget(tuple(manual_get["namespace"]), linked_ids[0]) is None
    assert (
        await StoreCapabilities(store, _AUTHORITY).read_documents(
            corpus="installation-docs",
            mode="exact",
            key=linked_ids[0],
            record_type="document",
            limit=1,
        )
        == []
    )
    assert linked_ids == ["doc-unavailable"]


@pytest.mark.asyncio
async def test_linked_full_content_is_not_automatically_injected_into_graph_context(
    monkeypatch,
):
    full_content = "FULL-CANONICAL-CONTENT-MUST-NOT-BE-AUTOMATIC-CONTEXT"
    store = InMemoryStore()
    await _seed_canonical_records(store, full_content)
    captured: dict = {}

    async def recording_invoke(
        _model, messages, _strategy, *, workspace, agent_context
    ):
        captured["messages"] = messages
        captured["workspace"] = workspace
        captured["agent_context"] = agent_context
        return JasperResponse(voice_text="No document was explicitly used.")

    monkeypatch.setattr(jasper_agent, "get_agent_llm", lambda _model: object())
    monkeypatch.setattr(jasper_agent, "select_response_strategy", lambda *_: "native")
    monkeypatch.setattr(jasper_agent, "_invoke_combined", recording_invoke)

    builder = StateGraph(jasper_agent.State)
    builder.add_node("jasper", jasper_agent.call_jasper)
    builder.add_edge(START, "jasper")
    builder.add_edge("jasper", END)
    graph = builder.compile(checkpointer=InMemorySaver(), store=store)
    config = {"configurable": {"thread_id": "thread-no-auto-content"}}
    result = await graph.ainvoke(
        {
            "messages": [
                {"role": "user", "content": "Answer without using a document"}
            ],
            "thread_identity": "thread-no-auto-content",
            "session_document_ids": ["doc-shared"],
        },
        config,
    )

    assert captured["agent_context"]["session_document_ids"] == ["doc-shared"]
    assert set(captured["agent_context"]) == {
        "session_document_ids",
        "thread_identity",
    }
    assert full_content not in repr(captured)
    assert full_content not in repr(result)
    checkpoint = await graph.checkpointer.aget_tuple(config)
    assert checkpoint is not None
    assert full_content not in repr(checkpoint.checkpoint)
    assert (
        await store.aget(
            documentation_namespace(_AUTHORITY, "installation-docs", "fragment"),
            "fragment-stable",
        )
    ).value["content"] == full_content
