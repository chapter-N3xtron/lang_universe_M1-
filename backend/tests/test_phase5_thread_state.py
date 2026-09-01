"""Focused contracts for Phase 5 checkpointed session document IDs."""

from __future__ import annotations

from typing import get_type_hints

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore

from src.chat_ui import State
from src.phase5_thread_state import (
    MAX_SESSION_DOCUMENT_IDS,
    normalize_session_document_ids,
    replace_session_document_ids,
)


def _checkpoint_graph(store: InMemoryStore):
    def normalize_links(state: State) -> dict[str, list[str]]:
        return {
            "session_document_ids": normalize_session_document_ids(
                state.get("session_document_ids", [])
            )
        }

    builder = StateGraph(State)
    builder.add_node("normalize_links", normalize_links)
    builder.add_edge(START, "normalize_links")
    builder.add_edge("normalize_links", END)
    return builder.compile(checkpointer=InMemorySaver(), store=store)


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_session_document_id_normalizer_is_ordered_bounded_and_id_only():
    assert normalize_session_document_ids(["doc-2", "doc-1", "doc-2", "Doc_3.v1"]) == [
        "doc-2",
        "doc-1",
        "Doc_3.v1",
    ]
    assert (
        len(
            normalize_session_document_ids(
                [f"doc-{index}" for index in range(MAX_SESSION_DOCUMENT_IDS)]
            )
        )
        == MAX_SESSION_DOCUMENT_IDS
    )
    assert normalize_session_document_ids(["doc-1"] * 101) == ["doc-1"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "doc-1",
        ("doc-1",),
        {"document_id": "doc-1"},
        [{"content": "body", "document_id": "doc-1"}],
        [{"tags": ["tag"], "document_id": "doc-1"}],
        [{"metadata": {"title": "Title"}, "document_id": "doc-1"}],
        [""],
        [" doc-1"],
        ["doc/1"],
        ["x" * 129],
        [1],
    ],
)
def test_session_document_id_normalizer_rejects_non_id_payloads(value):
    with pytest.raises(ValueError):
        normalize_session_document_ids(value)


def test_session_document_id_normalizer_rejects_more_than_100_unique_ids():
    with pytest.raises(ValueError, match="100 unique"):
        normalize_session_document_ids(
            [f"doc-{index}" for index in range(MAX_SESSION_DOCUMENT_IDS + 1)]
        )


@pytest.mark.asyncio
async def test_checkpoint_restores_same_thread_and_isolates_another_thread():
    store = InMemoryStore()
    graph = _checkpoint_graph(store)
    first = _config("thread-first")
    second = _config("thread-second")

    initial = await graph.ainvoke(
        {"session_document_ids": ["doc-2", "doc-1", "doc-2"]}, first
    )
    reopened = await graph.ainvoke({}, first)
    isolated = await graph.ainvoke({}, second)

    assert initial["session_document_ids"] == ["doc-2", "doc-1"]
    assert reopened["session_document_ids"] == ["doc-2", "doc-1"]
    assert isolated["session_document_ids"] == []


@pytest.mark.asyncio
async def test_complete_list_replacement_makes_empty_list_authoritative():
    graph = _checkpoint_graph(InMemoryStore())
    config = _config("thread-replacement")

    await graph.ainvoke({"session_document_ids": ["doc-1", "doc-2"]}, config)
    result = await graph.ainvoke({"session_document_ids": []}, config)

    assert result["session_document_ids"] == []
    assert graph.get_state(config).values["session_document_ids"] == []
    assert get_type_hints(State)["session_document_ids"] == list[str]
    annotation = get_type_hints(State, include_extras=True)["session_document_ids"]
    assert annotation.__metadata__ == (replace_session_document_ids,)


@pytest.mark.asyncio
async def test_real_graph_state_rejects_non_id_link_payloads():
    graph = _checkpoint_graph(InMemoryStore())

    with pytest.raises(ValueError, match="invalid document ID"):
        await graph.ainvoke(
            {"session_document_ids": [{"content": "not checkpoint link data"}]},
            _config("thread-invalid"),
        )


@pytest.mark.asyncio
async def test_many_threads_can_retain_same_id_without_store_writes():
    store = InMemoryStore()
    graph = _checkpoint_graph(store)
    configs = [_config(f"thread-{index}") for index in range(12)]

    for config in configs:
        await graph.ainvoke({"session_document_ids": ["shared-doc"]}, config)

    assert all(
        graph.get_state(config).values["session_document_ids"] == ["shared-doc"]
        for config in configs
    )
    checkpoint = graph.checkpointer.get_tuple(configs[0])
    assert checkpoint is not None
    assert checkpoint.checkpoint["channel_values"]["session_document_ids"] == [
        "shared-doc"
    ]
    assert await store.asearch(("app",), limit=1000) == []
