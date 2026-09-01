from datetime import UTC, datetime

import pytest
from langgraph.store.memory import InMemoryStore

from src.phase5_capabilities import (
    Authority,
    CapabilityError,
    StoreCapabilities,
    documentation_namespace,
)
from src.phase5_ingestion import (
    RAG_FRAGMENT_MAX_BYTES,
    DocumentationIngestionRequest,
    split_docling_text,
)
from src.phase5_ingestion import (
    supervisor_ingest_document as _supervisor_ingest_document,
)
from src.phase5_ingestion import (
    validate_ingestion_request as _validate_ingestion_request,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _enable_test_store_ttl(monkeypatch):
    monkeypatch.setattr(InMemoryStore, "supports_ttl", True)


def validate_ingestion_request(candidate, **kwargs):
    return _validate_ingestion_request(
        candidate,
        trusted_requester=candidate.requester,
        trusted_routing_origin="supervisor-handoff",
        source_approved=True,
        **kwargs,
    )


async def supervisor_ingest_document(candidate, **kwargs):
    return await _supervisor_ingest_document(
        candidate,
        trusted_requester=candidate.requester,
        trusted_routing_origin="supervisor-handoff",
        source_approved=True,
        **kwargs,
    )


AUTH = Authority(
    "tenant-1",
    "owner-1",
    corpus_read_grants=frozenset({"installation-docs"}),
)


def request(**changes):
    values = {
        "requester": "librarian",
        "corpus": "installation-docs",
        "document_id": "report-document",
        "document_ref": "upload:report.pdf",
        "fragment_id": "report-1",
        "operation_id": "ingest-1",
        "source_type": "owner-upload",
        "source_uri": "unknown",
        "title": "Report",
        "locator": "section-1",
        "source_revision": "git-1",
        "explicitly_selected": True,
    }
    values.update(changes)
    return DocumentationIngestionRequest(**values)


@pytest.mark.asyncio
async def test_supervisor_ingestion_writes_only_after_docling_ocr_success():
    store = InMemoryStore()

    async def ocr(_reference):
        return {"normalized": "ordered report", "layout_authority": "docling"}

    result = await supervisor_ingest_document(
        request(), store=store, installation_authority=AUTH, ocr=ocr, now=NOW
    )
    assert result["fragment_count"] == 1
    fragments = await store.asearch(documentation_namespace(AUTH, "installation-docs"))
    assert [item.value["content"] for item in fragments] == ["ordered report"]


@pytest.mark.asyncio
async def test_failed_ocr_and_sensitive_coder_file_create_no_corpus_record():
    store = InMemoryStore()

    async def failed(_reference):
        raise RuntimeError("synthetic OCR failure")

    with pytest.raises(CapabilityError, match="documentation_ingestion_failed"):
        await supervisor_ingest_document(
            request(), store=store, installation_authority=AUTH, ocr=failed, now=NOW
        )
    with pytest.raises(CapabilityError):
        await supervisor_ingest_document(
            request(
                requester="coder",
                source_type="coder-report",
                document_ref="credentials.md",
            ),
            store=store,
            installation_authority=AUTH,
            ocr=failed,
            now=NOW,
        )
    assert not await store.asearch(("app", "v1", "documentation-retrieval"))


@pytest.mark.asyncio
async def test_specialist_direct_document_write_is_denied():
    store = InMemoryStore()
    api = StoreCapabilities(
        store, Authority("tenant-1", "owner-1", principal_id="coder"), now=lambda: NOW
    )
    with pytest.raises(CapabilityError):
        await api.write_document(
            corpus="installation-docs",
            fragment_id="f1",
            content="report",
            provenance={},
            operation_id="direct-1",
            supervisor_approved=True,
            ocr_succeeded=True,
        )
    assert not await store.asearch(("app", "v1"))


def test_literal_private_sources_and_identity_alias_are_rejected():
    with pytest.raises(CapabilityError):
        validate_ingestion_request(
            request(
                source_uri="https://127.0.0.1/a.pdf",
                document_ref="https://127.0.0.1/a.pdf",
            )
        )
    with pytest.raises(CapabilityError):
        validate_ingestion_request(request(document_id="report-1"))


@pytest.mark.parametrize("requester", ["owner", "ocr", "supervisor", "unknown", ""])
def test_other_requesters_cannot_use_specialist_supervisor_handoff(requester):
    with pytest.raises(CapabilityError, match="Invalid trusted ingestion handoff"):
        validate_ingestion_request(request(requester=requester))


def test_owner_handoff_is_narrowly_limited_to_owner_upload():
    owner_upload = request(requester="owner")
    _validate_ingestion_request(
        owner_upload,
        trusted_requester="owner",
        trusted_routing_origin="owner-upload-graph",
        source_approved=True,
    )
    with pytest.raises(CapabilityError, match="Owner source type mismatch"):
        _validate_ingestion_request(
            request(requester="owner", source_type="approved-private-workspace"),
            trusted_requester="owner",
            trusted_routing_origin="owner-upload-graph",
            source_approved=True,
        )


@pytest.mark.asyncio
async def test_full_ingestion_provenance_and_content_free_denied_audit():
    store = InMemoryStore()

    async def ocr(_reference):
        return {"normalized": "layout text", "layout_authority": "docling"}

    record = await supervisor_ingest_document(
        request(), store=store, installation_authority=AUTH, ocr=ocr, now=NOW
    )
    assert record["document_id"] != record["fragment_ids"][0]
    fragment = (
        await store.asearch(
            documentation_namespace(AUTH, "installation-docs", "fragment")
        )
    )[0].value
    document = (
        await store.asearch(
            documentation_namespace(AUTH, "installation-docs", "document")
        )
    )[0].value
    assert fragment["document_id"] == record["document_id"]
    assert document["provenance"]["requester"] == "librarian"
    assert document["provenance"]["routing_origin"] == "supervisor-handoff"
    assert "locator" not in document["provenance"]

    with pytest.raises(CapabilityError) as failure:
        await supervisor_ingest_document(
            request(operation_id="bad-1", source_uri="https://localhost/x"),
            store=store,
            installation_authority=AUTH,
            ocr=ocr,
            now=NOW,
        )
    assert "localhost" not in str(failure.value)
    audits = await store.asearch(("app", "v1", "phase5-audit"), limit=20)
    denied = [item.value for item in audits if item.value["decision"] == "denied"]
    assert denied and all(
        "content" not in event and "query" not in event for event in denied
    )


@pytest.mark.parametrize("source_type", ["public-https", "public-pdf"])
def test_public_candidates_require_trusted_downloader_upload_evidence(source_type):
    with pytest.raises(CapabilityError, match="Approved upload reference"):
        validate_ingestion_request(
            request(
                source_type=source_type,
                source_uri="https://example.com/page.pdf",
                document_ref="https://example.com/page.pdf",
            )
        )


def test_librarian_owner_upload_reference_is_supported():
    validate_ingestion_request(request(document_ref="upload:opaque-1"))


def test_librarian_approved_private_workspace_and_outside_rejection(tmp_path):
    inside = tmp_path / "guide.pdf"
    inside.write_text("synthetic")
    validate_ingestion_request(
        request(source_type="approved-private-workspace", document_ref=str(inside)),
        selected_workspace=str(tmp_path),
        current_evidence=("guide.pdf",),
    )
    with pytest.raises(CapabilityError):
        validate_ingestion_request(
            request(
                source_type="approved-private-workspace", document_ref="../outside.pdf"
            ),
            selected_workspace=str(tmp_path),
            current_evidence=("../outside.pdf",),
        )


@pytest.mark.parametrize("suffix", [".md", ".txt", ".pdf", ".docx"])
def test_coder_qualifying_selected_artifact_matrix(tmp_path, suffix):
    path = tmp_path / f"report{suffix}"
    path.write_text("synthetic")
    validate_ingestion_request(
        request(
            requester="coder",
            source_type="coder-report",
            document_ref=str(path),
            source_uri="unknown",
        ),
        selected_workspace=str(tmp_path),
        current_evidence=(path.name,),
    )


@pytest.mark.parametrize(
    "name", ["report.py", "report.html", ".env", "secret.md", "credentials.txt"]
)
def test_coder_rejects_other_or_sensitive_artifacts(tmp_path, name):
    path = tmp_path / name
    path.write_text("synthetic")
    with pytest.raises(CapabilityError):
        validate_ingestion_request(
            request(
                requester="coder",
                source_type="coder-report",
                document_ref=str(path),
                source_uri="unknown",
            ),
            selected_workspace=str(tmp_path),
            current_evidence=(path.name,),
        )


@pytest.mark.asyncio
async def test_fragment_write_failure_is_sanitized_without_atomicity_claim():
    class FailingFragmentStore(InMemoryStore):
        async def aput(self, namespace, key, value, *, index=None, ttl=None):
            if namespace[-1] == "record:fragment":
                raise RuntimeError("backend credential=must-not-leak")
            return await super().aput(namespace, key, value, index=index, ttl=ttl)

    store = FailingFragmentStore()

    async def ocr(_reference):
        return {"normalized": "layout text", "layout_authority": "docling"}

    with pytest.raises(CapabilityError) as failure:
        await supervisor_ingest_document(
            request(), store=store, installation_authority=AUTH, ocr=ocr, now=NOW
        )
    assert "credential" not in str(failure.value)
    documents = await store.asearch(
        documentation_namespace(AUTH, "installation-docs", "document"), limit=1000
    )
    fragments = await store.asearch(
        documentation_namespace(AUTH, "installation-docs", "fragment"), limit=1000
    )
    assert len(documents) == 1 and "content" not in documents[0].value
    assert fragments == []


def test_untrusted_request_fields_cannot_attest_handoff_or_approval():
    candidate = request(
        requester="coder",
        source_type="coder-report",
        explicitly_selected=True,
        routing_origin="supervisor-handoff",
    )
    with pytest.raises(CapabilityError, match="trusted ingestion handoff"):
        _validate_ingestion_request(candidate, source_approved=True)


@pytest.mark.asyncio
async def test_complete_ordered_multi_fragment_docling_text_and_multiple_books_persist():
    store = InMemoryStore()
    first_text = "# Book one\n\n" + ("α section text\n\n" * 5000)
    second_text = "# Book two\n\n" + ("beta section text\n" * 4000)

    async def ingest_book(document_id, fragment_seed, text):
        async def ocr(_reference):
            return {"normalized": text, "layout_authority": "docling"}

        return await supervisor_ingest_document(
            request(
                document_id=document_id,
                fragment_id=fragment_seed,
                operation_id=f"operation-{document_id}",
                document_ref=f"upload:{document_id}.pdf",
                title=document_id,
            ),
            store=store,
            installation_authority=AUTH,
            ocr=ocr,
            now=NOW,
        )

    first = await ingest_book("book-one", "book-one-fragment", first_text)
    second = await ingest_book("book-two", "book-two-fragment", second_text)
    assert first["fragment_count"] > 1
    assert second["fragment_count"] > 1

    stored = await store.asearch(
        documentation_namespace(AUTH, "installation-docs", "fragment"), limit=1000
    )
    by_document = {"book-one": [], "book-two": []}
    for item in stored:
        value = item.value
        assert len(value["content"].encode("utf-8")) <= RAG_FRAGMENT_MAX_BYTES
        by_document[value["document_id"]].append(value)
    for document_id, original in (("book-one", first_text), ("book-two", second_text)):
        ordered = sorted(
            by_document[document_id], key=lambda row: int(row["fragment_index"])
        )
        assert "".join(row["content"] for row in ordered) == original
        assert [int(row["fragment_index"]) for row in ordered] == list(
            range(len(ordered))
        )
        assert all(int(row["fragment_count"]) == len(ordered) for row in ordered)

    documents = await store.asearch(
        documentation_namespace(AUTH, "installation-docs", "document"), limit=100
    )
    assert {item.key for item in documents} == {"book-one", "book-two"}
    assert all("locator" not in item.value["provenance"] for item in documents)


def test_docling_split_is_lossless_and_uses_utf8_safe_fallback():
    text = "# Heading\n\n" + "🙂" * 100 + "\nparagraph"
    pieces = split_docling_text(text, max_bytes=37)
    assert "".join(piece for piece, _, _ in pieces) == text
    assert all(len(piece.encode("utf-8")) <= 37 for piece, _, _ in pieces)
