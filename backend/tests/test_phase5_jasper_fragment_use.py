"""Focused contracts for Jasper's exact documentation-fragment use tool."""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain.tools import ToolRuntime
from langgraph.runtime import ServerInfo
from langgraph.store.memory import InMemoryStore

from src import chat_ui, jasper_agent
from src.phase5_capabilities import Authority, documentation_namespace
from src.phase5_tools import (
    CODER_PHASE5_TOOLS,
    JASPER_PHASE5_TOOLS,
    OCR_PHASE5_TOOLS,
)


class SyntheticOwner:
    identity = "owner-1"
    is_authenticated = True
    display_name = "Synthetic Owner"
    permissions: list[str] = []


class TrackingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.gets: list[tuple[tuple[str, ...], str]] = []
        self.searches: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    async def aget(self, namespace: tuple[str, ...], key: str):
        self.gets.append((namespace, key))
        return await super().aget(namespace, key)

    async def asearch(self, namespace_prefix: tuple[str, ...], **kwargs: Any):
        self.searches.append((namespace_prefix, kwargs))
        return await super().asearch(namespace_prefix, **kwargs)


@pytest.fixture(autouse=True)
def installation(monkeypatch):
    monkeypatch.setenv("INSTALLATION_TENANT_ID", "tenant-1")
    monkeypatch.setenv("INSTALLATION_OWNER_ID", "owner-1")
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


def _tool(name: str):
    return next(tool for tool in JASPER_PHASE5_TOOLS if tool.name == name)


def _runtime(store, ids: list[str] | None = None, *, thread_id: str = "thread-1"):
    return ToolRuntime(
        state={
            "messages": [],
            "thread_identity": thread_id,
            "session_document_ids": list(ids or []),
        },
        context=None,
        config={"configurable": {"thread_id": thread_id}},
        stream_writer=lambda _: None,
        tool_call_id="use-call-1",
        store=store,
        server_info=ServerInfo("assistant-1", "chat_ui", SyntheticOwner()),
    )


async def _seed(
    store: InMemoryStore,
    *,
    fragment_id: str = "frag-1",
    document_id: str = "doc-1",
    status: str = "active",
):
    authority = Authority("tenant-1", "owner-1")
    await store.aput(
        documentation_namespace(authority, "installation-docs", "document"),
        document_id,
        {
            "record_type": "document",
            "id": document_id,
            "corpus": "installation-docs",
            "source_status": status,
            "title": "Canonical title",
            "tags": [],
        },
        index=False,
    )
    await store.aput(
        documentation_namespace(authority, "installation-docs", "fragment"),
        fragment_id,
        {
            "record_type": "fragment",
            "id": fragment_id,
            "fragment_id": fragment_id,
            "document_id": document_id,
            "content": "One bounded canonical excerpt.",
            "locator": "section-1",
            "corpus": "installation-docs",
        },
        index=["content"],
    )


@pytest.mark.asyncio
async def test_search_is_read_only_and_never_links():
    store = TrackingStore()
    await _seed(store)
    runtime = _runtime(store, ["doc-existing"])

    result = await _tool("jasper_documentation_read").coroutine(
        mode="exact", runtime=runtime, key="frag-1", limit=1
    )

    assert result["ok"] is True
    assert runtime.state["session_document_ids"] == ["doc-existing"]
    assert "session_document_ids" not in result


@pytest.mark.asyncio
async def test_use_exact_reads_fragment_derives_document_and_returns_command():
    store = TrackingStore()
    await _seed(store)
    store.gets.clear()

    command = await _tool("jasper_documentation_fragment_use").coroutine(
        fragment_id="frag-1", runtime=_runtime(store)
    )

    assert command.update["session_document_ids"] == ["doc-1"]
    message = command.update["messages"][0]
    assert message.tool_call_id == "use-call-1"
    payload = json.loads(message.content)
    assert payload["ok"] is True
    assert payload["result"]["fragment_id"] == "frag-1"
    assert payload["result"]["content"] == "One bounded canonical excerpt."
    assert [key for _, key in store.gets] == ["frag-1", "doc-1"]
    assert store.searches == []


def test_use_tool_is_jasper_only_and_hides_all_scope_inputs():
    use_tool = _tool("jasper_documentation_fragment_use")
    schema = use_tool.tool_call_schema.model_json_schema()

    assert set(schema["properties"]) == {"fragment_id"}
    assert use_tool not in CODER_PHASE5_TOOLS
    assert use_tool not in OCR_PHASE5_TOOLS
    assert jasper_agent._specialists(None) == []


@pytest.mark.asyncio
async def test_use_is_idempotent_and_bound_failure_keeps_links_unchanged():
    store = TrackingStore()
    await _seed(store)
    use_tool = _tool("jasper_documentation_fragment_use")

    duplicate = await use_tool.coroutine(
        fragment_id="frag-1", runtime=_runtime(store, ["doc-1", "doc-1"])
    )
    assert duplicate.update["session_document_ids"] == ["doc-1"]

    full = [f"existing-{index}" for index in range(100)]
    refused = await use_tool.coroutine(
        fragment_id="frag-1", runtime=_runtime(store, full)
    )
    assert "session_document_ids" not in refused.update
    assert json.loads(refused.update["messages"][0].content) == {
        "ok": False,
        "status": "denied",
        "error": "fragment_use_failed",
    }


@pytest.mark.asyncio
async def test_missing_and_inactive_have_same_sanitized_failure():
    use_tool = _tool("jasper_documentation_fragment_use")
    missing = await use_tool.coroutine(
        fragment_id="frag-missing", runtime=_runtime(TrackingStore(), ["kept"])
    )
    inactive_store = TrackingStore()
    await _seed(inactive_store, status="quarantined")
    inactive = await use_tool.coroutine(
        fragment_id="frag-1", runtime=_runtime(inactive_store, ["kept"])
    )

    for command in (missing, inactive):
        assert set(command.update) == {"messages"}
        assert command.update["messages"][0].tool_call_id == "use-call-1"
    assert (
        missing.update["messages"][0].content == inactive.update["messages"][0].content
    )


def test_nested_and_outer_projections_carry_only_document_ids(monkeypatch):
    ids = ["doc-2", "doc-1"]
    nested = jasper_agent._prepare_jasper_input(
        {"jasper_request": {"messages": [], "session_document_ids": ids}}
    )
    nested_output = jasper_agent._normal_jasper_output(
        {"messages": [], "session_document_ids": ids}
    )
    assert nested["session_document_ids"] == ids
    assert nested_output["jasper_result"]["session_document_ids"] == ids

    monkeypatch.setattr(chat_ui, "create_jasper_graph", lambda: lambda state: state)
    graph = chat_ui.create_chat_ui()
    state = {
        "messages": [],
        "thread_identity": "thread-1",
        "session_document_ids": ids,
    }
    config = {"configurable": {"thread_id": "thread-1"}}
    prepared = graph.nodes["prepare_jasper"].runnable.invoke(state, config)
    assert prepared.update["jasper_request"]["session_document_ids"] == ids

    routed = graph.nodes["route_jasper_result"].runnable.invoke(
        {"jasper_result": {"session_document_ids": ids, "messages": []}}
    )
    assert routed.update["session_document_ids"] == ids
    assert all(type(item) is str for item in routed.update["session_document_ids"])
