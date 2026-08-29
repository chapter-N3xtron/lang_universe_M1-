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
    DocumentationIngestionRequest,
    supervisor_ingest_document,
    validate_ingestion_request,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
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
        "document_ref": "https://example.com/report.pdf",
        "fragment_id": "report-1",
        "operation_id": "ingest-1",
        "source_type": "public-pdf",
        "source_uri": "https://example.com/report.pdf",
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
    assert result["content"] == "ordered report"
    assert await store.asearch(documentation_namespace(AUTH, "installation-docs"))


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
            request(source_uri="https://127.0.0.1/a.pdf", document_ref="https://127.0.0.1/a.pdf")
        )
    with pytest.raises(CapabilityError):
        validate_ingestion_request(request(document_id="report-1"))


@pytest.mark.parametrize("requester", ["ocr", "supervisor", "unknown", ""])
def test_only_librarian_or_coder_can_request_ingestion(requester):
    with pytest.raises(CapabilityError, match="Unsupported ingestion requester"):
        validate_ingestion_request(request(requester=requester))


@pytest.mark.asyncio
async def test_full_ingestion_provenance_and_content_free_denied_audit():
    store = InMemoryStore()

    async def ocr(_reference):
        return {"normalized": "layout text", "layout_authority": "docling"}

    record = await supervisor_ingest_document(
        request(), store=store, installation_authority=AUTH, ocr=ocr, now=NOW
    )
    assert record["document_id"] != record["fragment_id"]
    assert record["provenance"] | {
        "requester": "librarian",
        "routing_origin": "jasper-supervisor-tool",
        "routing_exit": "ocr_exit",
        "ocr_authority": "docling",
        "supervisor_stage": "validated-after-ocr",
    } == record["provenance"]

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
    assert denied and all("content" not in event and "query" not in event for event in denied)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_type": "public-https", "source_uri": "https://example.com/page"},
        {"source_type": "public-pdf", "source_uri": "https://example.com/page.pdf"},
        {"source_type": "owner-upload", "source_uri": "unknown", "document_ref": "upload:opaque-1"},
    ],
)
def test_librarian_approved_public_and_upload_source_matrix(changes):
    validate_ingestion_request(request(**changes))


def test_librarian_approved_private_workspace_and_outside_rejection(tmp_path):
    inside = tmp_path / "guide.pdf"
    inside.write_text("synthetic")
    validate_ingestion_request(
        request(source_type="approved-private-workspace", document_ref=str(inside)),
        selected_workspace=str(tmp_path), current_evidence=("guide.pdf",),
    )
    with pytest.raises(CapabilityError):
        validate_ingestion_request(
            request(source_type="approved-private-workspace", document_ref="../outside.pdf"),
            selected_workspace=str(tmp_path), current_evidence=("../outside.pdf",),
        )


@pytest.mark.parametrize("suffix", [".md", ".txt", ".pdf", ".docx"])
def test_coder_qualifying_selected_artifact_matrix(tmp_path, suffix):
    path = tmp_path / f"report{suffix}"
    path.write_text("synthetic")
    validate_ingestion_request(
        request(requester="coder", source_type="coder-report", document_ref=str(path),
                source_uri="unknown"),
        selected_workspace=str(tmp_path), current_evidence=(path.name,),
    )


@pytest.mark.parametrize("name", ["report.py", "report.html", ".env", "secret.md", "credentials.txt"])
def test_coder_rejects_other_or_sensitive_artifacts(tmp_path, name):
    path = tmp_path / name
    path.write_text("synthetic")
    with pytest.raises(CapabilityError):
        validate_ingestion_request(
            request(requester="coder", source_type="coder-report", document_ref=str(path),
                    source_uri="unknown"),
            selected_workspace=str(tmp_path), current_evidence=(path.name,),
        )


@pytest.mark.asyncio
async def test_corpus_manifest_write_failure_rolls_back_fragment():
    class FailingManifestStore(InMemoryStore):
        async def aput(self, namespace, key, value, *, index=None, ttl=None):
            if namespace[-1] == "record:operation":
                raise RuntimeError("backend credential=must-not-leak")
            return await super().aput(namespace, key, value, index=index, ttl=ttl)

    store = FailingManifestStore()

    async def ocr(_reference):
        return {"normalized": "layout text", "layout_authority": "docling"}

    with pytest.raises(CapabilityError) as failure:
        await supervisor_ingest_document(
            request(), store=store, installation_authority=AUTH, ocr=ocr, now=NOW
        )
    assert "credential" not in str(failure.value)
    assert not await store.asearch(("app", "v1", "documentation-retrieval"), limit=1000)
