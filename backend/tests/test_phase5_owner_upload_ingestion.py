"""Focused authenticated owner-upload route and service contracts."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from src import ocr_agent, phase5_ingestion, phase5_routes
from src.installation_auth import OWNER_PERMISSIONS, TRUST_DOMAIN
from src.phase5_capabilities import Authority, documentation_namespace
from src.phase5_ingestion import RAG_FRAGMENT_MAX_BYTES


class SyntheticOwner:
    identity = "owner-1"
    is_authenticated = True
    tenant_id = "tenant-1"
    trust_domain = TRUST_DOMAIN
    owner_type = "person"
    owner_id = "owner-1"
    permissions = list(OWNER_PERMISSIONS)
    corpus_grants = ["installation-docs"]


class TrackingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.puts: list[tuple[tuple[str, ...], str]] = []

    async def aput(
        self, namespace: tuple[str, ...], key: str, value: dict, **kwargs: Any
    ) -> None:
        self.puts.append((namespace, key))
        await super().aput(namespace, key, value, **kwargs)


@pytest.fixture(autouse=True)
def installation(monkeypatch):
    monkeypatch.setenv("INSTALLATION_TENANT_ID", "tenant-1")
    monkeypatch.setenv("INSTALLATION_OWNER_ID", "owner-1")
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


def route_client(monkeypatch, store: InMemoryStore) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.scope["user"] = SyntheticOwner()
        return await call_next(request)

    app.include_router(phase5_routes.router)
    monkeypatch.setattr(phase5_routes, "get_store", lambda: store)
    return TestClient(app)


def operation(reference: str, **extra: Any) -> dict[str, Any]:
    return {
        "upload_reference": reference,
        "filename": "guide.pdf",
        "title": "Owner guide",
        "tags": ["Installation", "Guide"],
        **extra,
    }


def test_owner_upload_is_lossless_bounded_deduplicated_and_content_derived(
    tmp_path, monkeypatch
):
    reference = f"upload:{'a' * 32}-guide.pdf"
    source = tmp_path / reference.removeprefix("upload:")
    original_bytes = b"unchanged source PDF bytes"
    source.write_bytes(original_bytes)
    monkeypatch.setattr(ocr_agent, "OCR_UPLOAD_DIR", tmp_path)
    normalized = "# Whole book\n\n" + ("section with unicode αβγ\n\n" * 400)
    calls: list[tuple[Any, ...]] = []

    def fake_ocr(*args):
        calls.append(args)
        return {"normalized": normalized, "layout_authority": "docling"}

    monkeypatch.setattr(phase5_ingestion, "run_ocr", fake_ocr)
    store = TrackingStore()
    route = route_client(monkeypatch, store)

    response = route.post("/phase5/owner-upload", json=operation(reference))

    assert response.status_code == 200
    ingestion = response.json()
    assert set(ingestion) == {"ok", "status", "document_id", "fragment_count"}
    assert ingestion["ok"] is True
    assert ingestion["fragment_count"] > 1
    assert calls == [
        (
            "Ingest the explicitly selected owner document losslessly.",
            reference,
            None,
            "markdown",
        )
    ]
    assert source.read_bytes() == original_bytes

    authority = Authority("tenant-1", "owner-1")
    fragments = store.search(
        documentation_namespace(authority, "installation-docs", "fragment"),
        limit=1000,
    )
    ordered = sorted(fragments, key=lambda item: int(item.value["fragment_index"]))
    assert "".join(item.value["content"] for item in ordered) == normalized
    assert all(
        len(item.value["content"].encode("utf-8")) <= RAG_FRAGMENT_MAX_BYTES
        for item in ordered
    )
    documents = store.search(
        documentation_namespace(authority, "installation-docs", "document"),
        limit=1000,
    )
    assert len(documents) == 1
    assert documents[0].key == ingestion["document_id"]
    assert documents[0].value["source_type"] == "owner-upload"
    assert documents[0].value["tags"] == ["guide", "installation"]
    assert all(
        "title" not in item.value and "tags" not in item.value for item in ordered
    )
    assert any(
        item.value["operation"] == "ingestion"
        for item in store.search(
            (
                "app",
                "v1",
                "phase5-audit",
                "tenant:tenant-1",
                "trust:local-installation-v1",
                "owner:person:owner-1",
            ),
            limit=100,
        )
    )

    repeated_reference = f"upload:{'c' * 32}-guide.pdf"
    repeated_source = tmp_path / repeated_reference.removeprefix("upload:")
    repeated_source.write_bytes(original_bytes)
    repeated = route.post(
        "/phase5/owner-upload", json=operation(repeated_reference)
    ).json()
    assert repeated["document_id"] == ingestion["document_id"]
    assert repeated_source.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": "attacker"},
        {"corpus": "attacker"},
        {"requester": "librarian"},
        {"document_id": "chosen"},
        {"source_status": "active"},
        {"model": "chosen-model"},
    ],
)
def test_authority_and_model_overrides_are_sanitized_without_ocr_or_writes(
    tmp_path, monkeypatch, extra
):
    reference = f"upload:{'b' * 32}-guide.pdf"
    (tmp_path / reference.removeprefix("upload:")).write_bytes(b"source")
    monkeypatch.setattr(ocr_agent, "OCR_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        phase5_ingestion,
        "run_ocr",
        lambda *_: (_ for _ in ()).throw(AssertionError("OCR must not run")),
    )
    store = TrackingStore()

    result = route_client(monkeypatch, store).post(
        "/phase5/owner-upload", json=operation(reference, **extra)
    )

    assert result.status_code == 200
    assert result.json() == phase5_routes._INGESTION_FAILURE
    assert "attacker" not in result.text
    assert "chosen-model" not in result.text
    assert all(
        "documentation-retrieval" not in namespace for namespace, _ in store.puts
    )
    assert any("phase5-audit" in namespace for namespace, _ in store.puts)


@pytest.mark.parametrize(
    "reference",
    ["upload:../guide.pdf", "upload:not-preserved.pdf", "file:/tmp/guide.pdf"],
)
def test_only_approved_upload_boundary_is_accepted(tmp_path, monkeypatch, reference):
    monkeypatch.setattr(ocr_agent, "OCR_UPLOAD_DIR", tmp_path)
    store = TrackingStore()
    result = route_client(monkeypatch, store).post(
        "/phase5/owner-upload", json=operation(reference)
    )
    assert result.json() == phase5_routes._INGESTION_FAILURE
    assert all(
        "documentation-retrieval" not in namespace for namespace, _ in store.puts
    )
    assert any("phase5-audit" in namespace for namespace, _ in store.puts)
