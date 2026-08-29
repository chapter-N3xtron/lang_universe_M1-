"""Trusted supervisor boundary for documentation ingestion through the OCR graph."""

from __future__ import annotations

import hashlib
import ipaddress
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from src.phase5_capabilities import (
    AsyncStore,
    Authority,
    CapabilityError,
    Delegation,
    StoreCapabilities,
)

_ALLOWED_CODER_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".pdf", ".docx"})
_SENSITIVE_NAMES = frozenset({".env", "id_rsa", "id_ed25519", "credentials", "secrets"})
_PUBLIC_TYPES = frozenset({"public-https", "public-pdf"})
_FAILURE_CLASS = "documentation_ingestion_failed"


@dataclass(frozen=True)
class DocumentationIngestionRequest:
    """Untrusted candidate. Approval and write authority are intentionally absent."""

    requester: Literal["librarian", "coder"]
    corpus: str
    document_id: str
    document_ref: str
    fragment_id: str
    operation_id: str
    source_type: str
    title: str
    locator: str
    source_revision: str
    source_uri: str = "unknown"
    source_time: str = "unknown"
    explicitly_selected: bool = False
    selection_marker: str = ""
    workspace_root: str = ""
    routing_origin: str = "jasper-supervisor-tool"
    routing_exit: str = "ocr_exit"


def _public_https(uri: str) -> None:
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise CapabilityError("Public source must be an HTTPS URL")
    host = parsed.hostname.rstrip(".").casefold()
    if (
        host in {"localhost", "localhost.localdomain", "ip6-localhost"}
        or host.endswith((".local", ".localhost", ".internal", ".home", ".lan"))
    ):
        raise CapabilityError("Non-public source host denied")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise CapabilityError("Non-public source address denied")


def _workspace_source(
    request: DocumentationIngestionRequest,
    *,
    selected_workspace: str | None,
    current_evidence: tuple[str, ...],
) -> None:
    if not selected_workspace:
        raise CapabilityError("Selected workspace required")
    root = Path(selected_workspace).expanduser().resolve()
    candidate = Path(request.document_ref).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise CapabilityError("Workspace source is outside selected workspace") from exc
    expected = hashlib.sha256(f"{root}\n{relative}".encode()).hexdigest()
    evidence = {str(item) for item in current_evidence}
    if request.selection_marker != expected and relative not in evidence:
        raise CapabilityError("Workspace source lacks server-derived selection evidence")


def validate_ingestion_request(
    request: DocumentationIngestionRequest,
    *,
    selected_workspace: str | None = None,
    current_evidence: tuple[str, ...] = (),
) -> None:
    """Validate every untrusted source field without performing network I/O.

    DNS and redirect targets must be revalidated by the downloader immediately before
    every connection; this boundary only rejects deterministic literal local/private
    hosts and addresses.
    """

    if request.routing_origin != "jasper-supervisor-tool" or request.routing_exit != "ocr_exit":
        raise CapabilityError("Invalid ingestion route")
    if request.requester not in {"librarian", "coder"}:
        raise CapabilityError("Unsupported ingestion requester")
    if not request.document_id or request.document_id == request.fragment_id:
        raise CapabilityError("Document and fragment identities must be distinct")
    path = Path(request.document_ref.removeprefix("upload:"))
    if request.requester == "coder":
        if not request.explicitly_selected or path.suffix.casefold() not in _ALLOWED_CODER_SUFFIXES:
            raise CapabilityError("Coder artifact is not explicitly selected or qualifying")
        name = path.name.casefold()
        if name in _SENSITIVE_NAMES or any(word in name for word in ("secret", "credential", "private-key")):
            raise CapabilityError("Sensitive artifact is not eligible for ingestion")
        if request.source_type != "coder-report":
            raise CapabilityError("Coder source type mismatch")
        _workspace_source(
            request,
            selected_workspace=selected_workspace,
            current_evidence=current_evidence,
        )
    elif request.source_type not in _PUBLIC_TYPES | {"owner-upload", "approved-private-workspace"}:
        raise CapabilityError("Librarian source is not approved")
    if request.source_type in _PUBLIC_TYPES:
        _public_https(request.source_uri)
    elif request.source_type == "owner-upload":
        reference = request.document_ref
        upload_id = reference.removeprefix("upload:")
        if not reference.startswith("upload:") or not upload_id or any(part in upload_id for part in ("/", "\\", "..")):
            raise CapabilityError("Owner upload reference is invalid")
    elif request.source_type == "approved-private-workspace":
        _workspace_source(
            request,
            selected_workspace=selected_workspace,
            current_evidence=current_evidence,
        )


def sanitized_ingestion_failure(correlation_id: str) -> dict[str, str | bool]:
    return {"ok": False, "failure_class": _FAILURE_CLASS, "correlation_id": correlation_id}


async def supervisor_ingest_document(
    request: DocumentationIngestionRequest,
    *,
    store: AsyncStore,
    installation_authority: Authority,
    ocr: Callable[[str], Awaitable[dict[str, Any]]],
    now: datetime | None = None,
    selected_workspace: str | None = None,
    current_evidence: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Validate -> OCR -> mint expiring write delegation; audit every outcome."""

    current = now or datetime.now(UTC)
    correlation = f"ing-{uuid.uuid4().hex}"
    audit = StoreCapabilities(store, installation_authority, now=lambda: current)
    try:
        validate_ingestion_request(
            request,
            selected_workspace=selected_workspace,
            current_evidence=current_evidence,
        )
        if request.corpus not in installation_authority.corpus_read_grants:
            raise CapabilityError("Corpus grant denied")
        result = await ocr(request.document_ref)
        if (
            result.get("layout_authority") != "docling"
            or not isinstance(result.get("normalized"), str)
            or not result["normalized"]
        ):
            raise CapabilityError("OCR output rejected")
        content = result["normalized"]
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        authority = Authority(
            installation_authority.tenant_id,
            installation_authority.owner_id,
            principal_id="supervisor",
            corpus_read_grants=installation_authority.corpus_read_grants,
            delegation=Delegation(
                issuer="supervisor",
                subject="trusted-documentation-adapter",
                operations=frozenset({"documentation-retrieval:write"}),
                corpora=frozenset({request.corpus}),
                expires_at=current + timedelta(minutes=5),
                supervisor_created=True,
            ),
        )
        record = await StoreCapabilities(store, authority, now=lambda: current).write_document(
            corpus=request.corpus,
            fragment_id=request.fragment_id,
            content=content,
            operation_id=request.operation_id,
            supervisor_approved=True,
            ocr_succeeded=True,
            provenance={
                "document_id": request.document_id,
                "locator": request.locator,
                "title": request.title,
                "source_revision": request.source_revision,
                "digest": digest,
                "source_status": "active",
                "source_type": request.source_type,
                "source_uri": request.source_uri,
                "source_time": request.source_time,
                "requester": request.requester,
                "routing_origin": request.routing_origin,
                "routing_exit": request.routing_exit,
                "ocr_authority": "docling",
                "supervisor_stage": "validated-after-ocr",
            },
        )
        await audit.audit_event(
            operation="ingestion", record_id=request.document_id,
            correlation=correlation, decision="allowed", count=1, corpus=request.corpus,
            reason_class="policy",
        )
        return record
    except Exception as exc:
        with suppress(Exception):
            await audit.audit_event(
                operation="ingestion", record_id=request.document_id,
                correlation=correlation, decision="denied", count=0,
                corpus=request.corpus, reason_class="validation-or-backend",
            )
        error = CapabilityError(
            f"{_FAILURE_CLASS}; correlation_id={correlation}"
        )
        raise error from exc
