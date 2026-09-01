"""Source-isolated credential-boundary contracts for Phase 5.

These tests use synthetic values only. They do not inspect .env or claim anything about
request capture, logs, or tracing in a deployed Agent Server.
"""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, TypedDict
from unittest.mock import patch

import pytest
from langchain.tools import ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import ServerInfo
from langgraph.store.memory import InMemoryStore

import src.phase5_capabilities as p5
from src.phase5_capabilities import Authority, CapabilityError, StoreCapabilities
from src.phase5_ingestion import (
    DocumentationIngestionRequest,
    supervisor_ingest_document,
)
from src.phase5_tools import CODER_PHASE5_TOOLS, JASPER_PHASE5_TOOLS, _call

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PERSISTENCE_URI = "postgresql://phase5_user:phase5_password@db.invalid/phase5"
SOURCE_URI = "https://source_user:source_password@source.invalid/private.pdf"
SOURCE_TOKEN = "synthetic-source-token-value"
ENV = {
    "INSTALLATION_TENANT_ID": "tenant-1",
    "INSTALLATION_OWNER_ID": "owner-1",
    "INSTALLATION_OWNER_API_KEY": "synthetic-owner-api-key",
    "DATABASE_URI": PERSISTENCE_URI,
    "SOURCE_CONNECTION_URI": SOURCE_URI,
    "SOURCE_API_KEY": SOURCE_TOKEN,
}
SECRET_FIELDS = p5._OBVIOUS_SECRET_FIELDS | frozenset(
    {
        "database_uri",
        "postgres_uri",
        "connection_string",
        "connection_uri",
        "source_api_key",
        "username",
    }
)
HIDDEN_TOOL_FIELDS = SECRET_FIELDS | frozenset(
    {
        "runtime",
        "store",
        "authority",
        "namespace",
        "tenant",
        "tenant_id",
        "owner",
        "owner_id",
    }
)


@pytest.fixture(autouse=True)
def _enable_test_store_ttl(monkeypatch):
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


SYNTHETIC_SECRETS = tuple(
    value
    for key, value in ENV.items()
    if key not in {"INSTALLATION_TENANT_ID", "INSTALLATION_OWNER_ID"}
)


class SyntheticServerUser:
    identity = "owner-1"
    is_authenticated = True
    display_name = "Synthetic Owner"
    permissions: list[str] = []


class CredentialBearingStore(InMemoryStore):
    """A Store double whose backend-only attributes must never become graph data."""

    connection_uri = PERSISTENCE_URI
    source_api_key = SOURCE_TOKEN


def runtime(store: InMemoryStore) -> ToolRuntime:
    return ToolRuntime(
        state={"messages": []},
        context=None,
        config={"configurable": {"thread_id": "credential-proof"}},
        stream_writer=lambda _: None,
        tool_call_id="credential-proof-call",
        store=store,
        server_info=ServerInfo("assistant-1", "chat_ui", SyntheticServerUser()),
    )


def property_names(schema: Any) -> set[str]:
    if isinstance(schema, dict):
        names = set(schema.get("properties", {}))
        return names | set().union(
            *(property_names(value) for value in schema.values())
        )
    if isinstance(schema, list):
        return set().union(*(property_names(value) for value in schema))
    return set()


def assert_no_synthetic_credentials(value: Any) -> None:
    serialized = json.dumps(value, default=str, sort_keys=True).casefold()
    assert all(secret.casefold() not in serialized for secret in SYNTHETIC_SECRETS)
    if isinstance(value, dict):
        assert not ({str(key).casefold() for key in value} & SECRET_FIELDS)
        for item in value.values():
            assert_no_synthetic_credentials(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_no_synthetic_credentials(item)


def test_model_tool_schemas_and_arguments_hide_runtime_scope_and_credentials():
    tools = (*JASPER_PHASE5_TOOLS, *CODER_PHASE5_TOOLS)
    for phase5_tool in tools:
        schema = phase5_tool.tool_call_schema.model_json_schema()
        assert not (property_names(schema) & HIDDEN_TOOL_FIELDS)
        assert_no_synthetic_credentials(schema)

    model_supplied_arguments = {
        "kind": "task outcomes",
        "mode": "lexical",
        "query": "synthetic",
        "filters": {},
        "limit": 10,
    }
    assert not (set(model_supplied_arguments) & HIDDEN_TOOL_FIELDS)
    assert_no_synthetic_credentials(model_supplied_arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", sorted(p5._OBVIOUS_SECRET_FIELDS))
async def test_every_common_secret_field_is_rejected_before_memory_write(field):
    store = CredentialBearingStore()
    api = StoreCapabilities(
        store,
        Authority("tenant-1", "owner-1", memory_grants=frozenset({"write"})),
        now=lambda: NOW,
    )
    with pytest.raises(CapabilityError, match="credential fields"):
        await api.write_memory(
            kind="task outcomes",
            content="ordinary content",
            metadata={field: SOURCE_TOKEN},
            provenance={"source_type": "session", "source_id": "s1", "actor": "jasper"},
            operation_id="rejected-secret-field",
        )
    assert await store.asearch(("app",), limit=1000) == []


@pytest.mark.asyncio
async def test_backend_credentials_stay_out_of_normal_result_context_state_and_audit():
    store = CredentialBearingStore()
    selected = next(
        tool for tool in JASPER_PHASE5_TOOLS if tool.name == "jasper_memory_write"
    )
    tool_runtime = runtime(store)

    with patch.dict(os.environ, ENV, clear=False):
        result = await selected.coroutine(
            kind="task outcomes",
            content="credential boundary proof",
            metadata={"fixture": "synthetic"},
            source_type="session",
            source_id="s1",
            operation_id="credential-proof-write",
            runtime=tool_runtime,
        )

    assert result["ok"] is True
    assert tool_runtime.state == {"messages": []}
    assert tool_runtime.context is None
    assert_no_synthetic_credentials(result)
    audits = [
        item.value
        for item in await store.asearch(("app", "v1", "phase5-audit"), limit=20)
    ]
    assert audits
    for event in audits:
        assert_no_synthetic_credentials(event)


@pytest.mark.asyncio
async def test_backend_exception_is_sanitized_in_graph_state_result_and_audit():
    exception_text = (
        f"connection_string={PERSISTENCE_URI} source={SOURCE_URI} "
        f"password=synthetic api_key={SOURCE_TOKEN} authorization=Bearer-synthetic"
    )

    class FailingStore(CredentialBearingStore):
        async def asearch(self, namespace_prefix, **kwargs):
            if namespace_prefix[:3] == ("app", "v1", "cross-session-memory"):
                raise RuntimeError(exception_text)
            return await super().asearch(namespace_prefix, **kwargs)

    class ProofState(TypedDict):
        result: dict[str, Any]

    store = FailingStore()
    tool_runtime = runtime(store)

    async def tool_node(_state: ProofState) -> dict[str, Any]:
        return {
            "result": await _call(
                "jasper",
                tool_runtime,
                "read",
                lambda api: api.read_memory(
                    kind="task outcomes", mode="lexical", query="synthetic"
                ),
            )
        }

    builder = StateGraph(ProofState)
    builder.add_node("tool", tool_node)
    builder.add_edge(START, "tool")
    builder.add_edge("tool", END)
    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "credential-failure-proof"}}
    with patch.dict(os.environ, ENV, clear=False):
        state = await graph.ainvoke({"result": {}}, config)

    assert state == {
        "result": {"ok": False, "status": "partial", "error": "operation_failed"}
    }
    checkpoint = await checkpointer.aget_tuple(config)
    assert checkpoint is not None
    assert_no_synthetic_credentials(state)
    assert_no_synthetic_credentials(checkpoint.checkpoint)
    audits = [
        item.value
        for item in await store.asearch(("app", "v1", "phase5-audit"), limit=20)
    ]
    assert audits and audits[-1]["decision"] == "denied"
    for event in audits:
        assert_no_synthetic_credentials(event)


@pytest.mark.asyncio
async def test_ingestion_exception_and_credentialed_source_return_only_sanitized_failure_and_audit():
    request = DocumentationIngestionRequest(
        requester="librarian",
        corpus="installation-docs",
        document_id="credential-source",
        document_ref=SOURCE_URI,
        fragment_id="fragment-1",
        operation_id="credential-ingestion",
        source_type="public-pdf",
        title="Synthetic",
        locator="page-1",
        source_revision="r1",
        source_uri=SOURCE_URI,
    )
    store = CredentialBearingStore()
    authority = Authority(
        "tenant-1",
        "owner-1",
        corpus_read_grants=frozenset({"installation-docs"}),
    )

    async def credentialed_backend(_reference: str) -> dict[str, Any]:
        raise RuntimeError(
            f"password=synthetic api_key={SOURCE_TOKEN} database={PERSISTENCE_URI}"
        )

    failures = []
    for candidate in (
        request,
        replace(
            request,
            document_ref="https://example.invalid/private.pdf",
            source_uri="https://example.invalid/private.pdf",
            operation_id="credential-backend-ingestion",
        ),
    ):
        with pytest.raises(CapabilityError) as failure:
            await supervisor_ingest_document(
                candidate,
                store=store,
                installation_authority=authority,
                ocr=credentialed_backend,
                now=NOW,
            )
        failures.append(str(failure.value))

    assert all(
        error.startswith("documentation_ingestion_failed; correlation_id=ing-")
        for error in failures
    )
    for visible_error in failures:
        assert_no_synthetic_credentials(visible_error)
    audits = [
        item.value
        for item in await store.asearch(("app", "v1", "phase5-audit"), limit=20)
    ]
    assert len(audits) == 2 and all(event["decision"] == "denied" for event in audits)
    for event in audits:
        assert_no_synthetic_credentials(event)
