"""Focused authenticated Installation Library route contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from src import phase5_routes
from src.installation_auth import OWNER_PERMISSIONS, TRUST_DOMAIN
from src.phase5_capabilities import Authority, documentation_namespace


class SyntheticOwner:
    def __init__(self, *, identity: str = "owner-1", authenticated: bool = True):
        self.identity = identity
        self.is_authenticated = authenticated
        self.tenant_id = "tenant-1"
        self.trust_domain = TRUST_DOMAIN
        self.owner_type = "person"
        self.owner_id = "owner-1"
        self.permissions = list(OWNER_PERMISSIONS)
        self.corpus_grants = ["installation-docs"]


class NativeRankingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.semantic_calls: list[dict[str, Any]] = []

    async def asearch(self, namespace_prefix: tuple[str, ...], **kwargs: Any):
        if kwargs.get("query"):
            self.semantic_calls.append({"namespace": namespace_prefix, **kwargs})
            fragment_ns = documentation_namespace(
                Authority("tenant-1", "owner-1"),
                "installation-docs",
                "fragment",
            )
            return [
                SimpleNamespace(
                    key="fragment-b-1",
                    namespace=fragment_ns,
                    score=0.91,
                    value={
                        "record_type": "fragment",
                        "document_id": "doc-b",
                        "content": "private body B",
                    },
                ),
                SimpleNamespace(
                    key="fragment-b-2",
                    namespace=fragment_ns,
                    score=0.88,
                    value={
                        "record_type": "fragment",
                        "document_id": "doc-b",
                        "content": "second private body B",
                    },
                ),
                SimpleNamespace(
                    key="fragment-a-1",
                    namespace=fragment_ns,
                    score=0.72,
                    value={
                        "record_type": "fragment",
                        "document_id": "doc-a",
                        "content": "private body A",
                    },
                ),
            ]
        return await super().asearch(namespace_prefix, **kwargs)


@pytest.fixture(autouse=True)
def installation(monkeypatch):
    monkeypatch.setenv("INSTALLATION_TENANT_ID", "tenant-1")
    monkeypatch.setenv("INSTALLATION_OWNER_ID", "owner-1")
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


def document_namespace() -> tuple[str, ...]:
    return documentation_namespace(
        Authority("tenant-1", "owner-1"), "installation-docs", "document"
    )


def seed_document(store: InMemoryStore, document_id: str, status: str = "active"):
    store.put(
        document_namespace(),
        document_id,
        {
            "schema_version": 1,
            "record_type": "document",
            "id": document_id,
            "source_status": status,
            "title": f"Title {document_id}",
            "source_type": "owner-upload",
            "source_revision": "revision-1",
            "source_uri": "unknown",
            "tags": ["guide"],
            "digest": "must-not-project",
            "provenance": {"locator": "must-not-project"},
        },
        index=False,
    )


def client(monkeypatch, store: InMemoryStore, user: SyntheticOwner) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.scope["user"] = user
        return await call_next(request)

    app.include_router(phase5_routes.router)
    monkeypatch.setattr(phase5_routes, "get_store", lambda: store)
    return TestClient(app)


def audits(store: InMemoryStore):
    authority = Authority("tenant-1", "owner-1")
    namespace = (
        "app",
        "v1",
        "phase5-audit",
        "tenant:tenant-1",
        f"trust:{authority.trust_domain}",
        "owner:person:owner-1",
    )
    return store.search(namespace, limit=100)


def test_semantic_route_preserves_native_order_audits_and_omits_content(monkeypatch):
    store = NativeRankingStore()
    seed_document(store, "doc-a")
    seed_document(store, "doc-b")

    response = client(monkeypatch, store, SyntheticOwner()).post(
        "/phase5/installation-library",
        json={"operation": "semantic", "query": "bounded native query", "limit": 20},
    )

    assert response.status_code == 200
    result = response.json()
    assert [item["id"] for item in result["documents"]] == ["doc-b", "doc-a"]
    assert [item["score"] for item in result["documents"]] == [0.91, 0.72]
    assert all(
        set(item) <= set(phase5_routes._DOCUMENT_FIELDS) for item in result["documents"]
    )
    assert "private body" not in repr(result)
    assert store.semantic_calls[0]["query"] == "bounded native query"
    assert any(
        item.value["operation"] == "documentation-read" for item in audits(store)
    )


def test_resolve_filters_inactive_and_bounds_fail_with_sanitized_audit(monkeypatch):
    store = NativeRankingStore()
    seed_document(store, "active-doc")
    seed_document(store, "inactive-doc", "withdrawn")
    route = client(monkeypatch, store, SyntheticOwner())

    exact = route.post(
        "/phase5/installation-library",
        json={
            "operation": "resolve",
            "document_ids": ["inactive-doc", "active-doc"],
            "limit": 2,
        },
    ).json()
    denied = route.post(
        "/phase5/installation-library",
        json={"operation": "metadata", "limit": 21, "owner_id": "attacker"},
    ).json()

    assert [item["id"] for item in exact["documents"]] == ["active-doc"]
    assert denied == phase5_routes._LIBRARY_FAILURE
    assert any(item.value["decision"] == "denied" for item in audits(store))
    assert "attacker" not in repr(audits(store))


@pytest.mark.parametrize(
    "user,status",
    [
        (SyntheticOwner(authenticated=False), 401),
        (SyntheticOwner(identity="other"), 403),
    ],
)
def test_route_rejects_unauthenticated_or_non_installation_identity(
    monkeypatch, user, status
):
    store = NativeRankingStore()
    response = client(monkeypatch, store, user).post(
        "/phase5/installation-library",
        json={"operation": "metadata", "limit": 1},
    )
    assert response.status_code == status
    assert store.list_namespaces() == []
