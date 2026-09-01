"""Authenticated public-document route and ingestion boundary contracts."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from src import document_attachments, ocr_agent, phase5_ingestion, phase5_routes
from src.installation_auth import OWNER_PERMISSIONS, TRUST_DOMAIN
from src.phase5_capabilities import Authority, documentation_namespace
from src.phase5_public_download import PublicDownload


class Owner:
    identity = "owner-1"
    is_authenticated = True
    tenant_id = "tenant-1"
    trust_domain = TRUST_DOMAIN
    owner_type = "person"
    owner_id = "owner-1"
    permissions = list(OWNER_PERMISSIONS)
    corpus_grants = ["installation-docs"]


@pytest.fixture(autouse=True)
def installation(monkeypatch):
    monkeypatch.setenv("INSTALLATION_TENANT_ID", "tenant-1")
    monkeypatch.setenv("INSTALLATION_OWNER_ID", "owner-1")
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


def client(monkeypatch, store, user: Any = None) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if user is not False:
            request.scope["user"] = user or Owner()
        return await call_next(request)

    app.include_router(phase5_routes.router)
    monkeypatch.setattr(phase5_routes, "get_store", lambda: store)
    return TestClient(app)


def test_auth_happens_before_store_or_ingestion(monkeypatch):
    monkeypatch.setattr(
        phase5_routes,
        "get_store",
        lambda: (_ for _ in ()).throw(AssertionError("store must not resolve")),
    )
    route = client(monkeypatch, InMemoryStore(), user=False)
    response = route.post(
        "/phase5/public-document",
        json={"url": "https://public.example/page", "title": "Guide"},
    )
    assert response.status_code == 401


def test_route_passes_only_bounded_public_contract_and_sanitizes_result(
    monkeypatch,
):
    received: list[dict[str, Any]] = []

    async def ingest(operation, *, store):
        received.append(operation)
        assert isinstance(store, InMemoryStore)
        return {
            "document_id": "public-document-safe",
            "fragment_count": 3,
            "fragment_ids": ["private-fragment"],
            "document_digest": "private-digest",
        }

    monkeypatch.setattr(phase5_routes, "ingest_public_https", ingest)
    response = client(monkeypatch, InMemoryStore()).post(
        "/phase5/public-document",
        json={
            "url": "https://public.example/page.pdf",
            "title": "Public guide",
            "tags": ["Guide"],
        },
    )
    assert response.json() == {
        "ok": True,
        "status": "complete",
        "document_id": "public-document-safe",
        "fragment_count": 3,
    }
    assert received == [
        {
            "url": "https://public.example/page.pdf",
            "title": "Public guide",
            "tags": ["Guide"],
        }
    ]


def test_downloaded_bytes_cross_upload_boundary_and_docling_writes_canonical_fragments(
    tmp_path, monkeypatch
):
    source = b"<html><body>preserved source</body></html>"
    normalized = "# Public guide\n\n" + ("ordered section αβγ\n\n" * 250)
    monkeypatch.setattr(document_attachments, "OCR_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(ocr_agent, "OCR_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        phase5_ingestion,
        "download_public_document",
        lambda _url: PublicDownload(
            body=source,
            final_url="https://public.example/guide?revision=1",
            content_type="text/html",
            source_type="public-https",
            extension=".html",
        ),
    )
    ocr_calls: list[tuple[Any, ...]] = []

    def ocr(*args):
        ocr_calls.append(args)
        return {"layout_authority": "docling", "normalized": normalized}

    monkeypatch.setattr(phase5_ingestion, "run_ocr", ocr)
    store = InMemoryStore()
    response = client(monkeypatch, store).post(
        "/phase5/public-document",
        json={
            "url": "https://public.example/guide?revision=1",
            "title": "Public guide",
            "tags": ["Public", "Guide"],
        },
    )
    result = response.json()
    assert result["ok"] is True
    assert result["document_id"].startswith("public-document-")
    assert result["fragment_count"] > 1
    assert len(ocr_calls) == 1
    reference = ocr_calls[0][1]
    assert reference.startswith("upload:")
    preserved = tmp_path / reference.removeprefix("upload:")
    assert preserved.read_bytes() == source

    authority = Authority("tenant-1", "owner-1")
    fragments = store.search(
        documentation_namespace(authority, "installation-docs", "fragment"),
        limit=1000,
    )
    ordered = sorted(fragments, key=lambda item: int(item.value["fragment_index"]))
    assert "".join(item.value["content"] for item in ordered) == normalized
    assert all(len(item.value["content"].encode()) <= 1800 for item in ordered)
    documents = store.search(
        documentation_namespace(authority, "installation-docs", "document"), limit=10
    )
    assert documents[0].value["source_type"] == "public-https"
    assert documents[0].value["source_uri"] == "https://public.example/guide?revision=1"


def test_download_failure_is_sanitized_and_writes_no_document(monkeypatch):
    store = InMemoryStore()
    monkeypatch.setattr(
        phase5_ingestion,
        "download_public_document",
        lambda _url: (_ for _ in ()).throw(
            RuntimeError("https://public.example/file?private=query downloaded-body")
        ),
    )
    response = client(monkeypatch, store).post(
        "/phase5/public-document",
        json={
            "url": "https://public.example/file?private=query",
            "title": "Guide",
        },
    )
    assert response.json() == phase5_routes._INGESTION_FAILURE
    assert "private" not in response.text
    assert "downloaded-body" not in response.text
    authority = Authority("tenant-1", "owner-1")
    assert not store.search(
        documentation_namespace(authority, "installation-docs", "document"), limit=10
    )
    assert not store.search(
        documentation_namespace(authority, "installation-docs", "fragment"), limit=10
    )


@pytest.mark.parametrize(
    "forged",
    [
        {"corpus": "attacker"},
        {"requester": "librarian"},
        {"routing_origin": "model"},
        {"source_status": "active"},
        {"document_id": "chosen"},
        {"model": "chosen"},
    ],
)
def test_forged_authority_fields_fail_without_ingestion(monkeypatch, forged):
    monkeypatch.setattr(
        phase5_ingestion,
        "download_public_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid contract must not download")
        ),
    )
    operation = {
        "url": "https://public.example/page",
        "title": "Guide",
        **forged,
    }
    result = client(monkeypatch, InMemoryStore()).post(
        "/phase5/public-document", json=operation
    )
    assert result.json() == phase5_routes._INGESTION_FAILURE
    assert "attacker" not in result.text
    assert "chosen" not in result.text
