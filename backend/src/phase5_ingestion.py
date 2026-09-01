"""Trusted supervisor boundary for documentation ingestion through the OCR graph."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from src.document_attachments import preserve_ocr_upload, supported_extensions
from src.installation_auth import installation_identity
from src.ocr_agent import approved_document_path, run_ocr
from src.phase5_capabilities import (
    CANONICAL_DOCUMENTATION_CORPUS,
    MAX_DOCUMENT_TAG_BYTES,
    MAX_DOCUMENT_TAGS,
    MAX_ITEM_BYTES,
    AsyncStore,
    Authority,
    CapabilityError,
    Delegation,
    StoreCapabilities,
)
from src.phase5_public_download import download_public_document

_ALLOWED_CODER_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".pdf", ".docx"})
_SENSITIVE_NAMES = frozenset({".env", "id_rsa", "id_ed25519", "credentials", "secrets"})
_PUBLIC_TYPES = frozenset({"public-https", "public-pdf"})
_FAILURE_CLASS = "documentation_ingestion_failed"
# embeddinggemma is deployed with a 2,048-token context. This deliberately small
# UTF-8 byte ceiling leaves ample room for provider tokenization and request framing.
RAG_FRAGMENT_MAX_BYTES = 1800


@dataclass(frozen=True)
class DocumentationIngestionRequest:
    """Untrusted candidate. Approval and write authority are intentionally absent."""

    requester: Literal["owner", "librarian", "coder"]
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
    tags: tuple[str, ...] = ()
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
    if host in {"localhost", "localhost.localdomain", "ip6-localhost"} or host.endswith(
        (".local", ".localhost", ".internal", ".home", ".lan")
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
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise CapabilityError("Workspace source is outside selected workspace") from exc
    expected = hashlib.sha256(f"{root}\n{relative}".encode()).hexdigest()
    evidence = {str(item) for item in current_evidence}
    if request.selection_marker != expected and relative not in evidence:
        raise CapabilityError(
            "Workspace source lacks server-derived selection evidence"
        )


def validate_ingestion_request(
    request: DocumentationIngestionRequest,
    *,
    trusted_requester: Literal["owner", "librarian", "coder"] | None = None,
    trusted_routing_origin: str | None = None,
    source_approved: bool = False,
    selected_workspace: str | None = None,
    current_evidence: tuple[str, ...] = (),
) -> None:
    """Validate an untrusted candidate against a trusted supervisor handoff.

    Request fields never attest identity, routing origin, source approval, or workspace
    selection. Public classes are accepted only from the server-only bounded downloader
    origin and still reach OCR through an approved local upload reference.
    """

    valid_handoff = (
        trusted_requester == "owner"
        and request.requester == "owner"
        and trusted_routing_origin
        in {"owner-upload-graph", "owner-upload-route", "owner-public-url-route"}
        and request.routing_exit == "ocr_exit"
    ) or (
        trusted_requester in {"librarian", "coder"}
        and request.requester == trusted_requester
        and trusted_routing_origin == "supervisor-handoff"
        and request.routing_exit == "ocr_exit"
    )
    if not valid_handoff:
        raise CapabilityError("Invalid trusted ingestion handoff")
    if not source_approved:
        raise CapabilityError("Source approval evidence required")
    if not request.document_id or request.document_id == request.fragment_id:
        raise CapabilityError("Document and fragment identities must be distinct")
    path = Path(request.document_ref.removeprefix("upload:"))
    if request.requester == "coder":
        if (
            not request.explicitly_selected
            or path.suffix.casefold() not in _ALLOWED_CODER_SUFFIXES
        ):
            raise CapabilityError(
                "Coder artifact is not explicitly selected or qualifying"
            )
        name = path.name.casefold()
        if name in _SENSITIVE_NAMES or any(
            word in name for word in ("secret", "credential", "private-key")
        ):
            raise CapabilityError("Sensitive artifact is not eligible for ingestion")
        if request.source_type != "coder-report":
            raise CapabilityError("Coder source type mismatch")
        _workspace_source(
            request,
            selected_workspace=selected_workspace,
            current_evidence=current_evidence,
        )
    elif request.requester == "owner":
        allowed_owner_types = (
            _PUBLIC_TYPES
            if trusted_routing_origin == "owner-public-url-route"
            else {"owner-upload"}
        )
        if request.source_type not in allowed_owner_types:
            raise CapabilityError("Owner source type mismatch")
    elif request.source_type not in _PUBLIC_TYPES | {
        "owner-upload",
        "approved-private-workspace",
    }:
        raise CapabilityError("Librarian source is not approved")
    if request.source_type in _PUBLIC_TYPES:
        _public_https(request.source_uri)
    if request.source_type in _PUBLIC_TYPES | {"owner-upload"}:
        reference = request.document_ref
        upload_id = reference.removeprefix("upload:")
        if (
            not reference.startswith("upload:")
            or not upload_id
            or any(part in upload_id for part in ("/", "\\", ".."))
        ):
            raise CapabilityError("Approved upload reference is invalid")
    elif request.source_type == "approved-private-workspace":
        _workspace_source(
            request,
            selected_workspace=selected_workspace,
            current_evidence=current_evidence,
        )


def split_docling_text(
    text: str, *, max_bytes: int = RAG_FRAGMENT_MAX_BYTES
) -> list[tuple[str, int, int]]:
    """Split ordered Docling text without loss, preferring Markdown structure."""

    if (
        type(text) is not str
        or not text
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= RAG_FRAGMENT_MAX_BYTES
        or max_bytes > MAX_ITEM_BYTES
    ):
        raise CapabilityError("OCR output rejected")
    fragments: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        used = 0
        hard_end = start
        while hard_end < len(text):
            width = len(text[hard_end].encode("utf-8"))
            if used + width > max_bytes:
                break
            used += width
            hard_end += 1
        if hard_end == start:
            raise CapabilityError("OCR character exceeds fragment byte bound")
        end = hard_end
        if hard_end < len(text):
            window = text[start:hard_end]
            preferred: list[int] = []
            preferred.extend(
                match.end() for match in re.finditer(r"\n[ \t]*\n+", window)
            )
            preferred.extend(
                match.start() + 1 for match in re.finditer(r"\n#{1,6}[ \t]+", window)
            )
            if not preferred:
                preferred.extend(match.end() for match in re.finditer(r"\n", window))
            usable = [position for position in preferred if position > 0]
            if usable:
                end = start + max(usable)
        fragments.append((text[start:end], start, end))
        start = end
    if "".join(fragment for fragment, _, _ in fragments) != text:
        raise CapabilityError("OCR fragmentation failed")
    return fragments


def sanitized_ingestion_failure(correlation_id: str) -> dict[str, str | bool]:
    return {
        "ok": False,
        "failure_class": _FAILURE_CLASS,
        "correlation_id": correlation_id,
    }


async def supervisor_ingest_document(
    request: DocumentationIngestionRequest,
    *,
    store: AsyncStore,
    installation_authority: Authority,
    ocr: Callable[[str], Awaitable[dict[str, Any]]],
    trusted_requester: Literal["owner", "librarian", "coder"] | None = None,
    trusted_routing_origin: str | None = None,
    source_approved: bool = False,
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
            trusted_requester=trusted_requester,
            trusted_routing_origin=trusted_routing_origin,
            source_approved=source_approved,
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
        document_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        pieces = split_docling_text(content)
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
        api = StoreCapabilities(store, authority, now=lambda: current)
        fragment_ids: list[str] = []
        for index, (fragment_content, start, end) in enumerate(pieces):
            fragment_digest = hashlib.sha256(
                fragment_content.encode("utf-8")
            ).hexdigest()
            fragment_id = (
                request.fragment_id
                if len(pieces) == 1
                else hashlib.sha256(
                    f"{request.fragment_id}:{index}:{fragment_digest}".encode()
                ).hexdigest()
            )
            operation_id = (
                request.operation_id
                if len(pieces) == 1
                else hashlib.sha256(
                    f"{request.operation_id}:{index}:{fragment_digest}".encode()
                ).hexdigest()
            )
            locator = f"{request.locator}#docling-text={start}-{end}"
            if len(locator.encode("utf-8")) > 1024:
                raise CapabilityError("Fragment locator exceeds bounds")
            await api.write_document(
                corpus=request.corpus,
                fragment_id=fragment_id,
                content=fragment_content,
                tags=request.tags,
                operation_id=operation_id,
                supervisor_approved=True,
                ocr_succeeded=True,
                provenance={
                    "document_id": request.document_id,
                    "locator": locator,
                    "fragment_index": str(index),
                    "fragment_count": str(len(pieces)),
                    "char_start": str(start),
                    "char_end": str(end),
                    "title": request.title,
                    "source_revision": request.source_revision,
                    "digest": fragment_digest,
                    "document_digest": document_digest,
                    "source_status": "active",
                    "source_type": request.source_type,
                    "source_uri": request.source_uri,
                    "source_time": request.source_time,
                    "requester": trusted_requester,
                    "routing_origin": trusted_routing_origin,
                    "routing_exit": request.routing_exit,
                    "ocr_authority": "docling",
                    "supervisor_stage": "validated-after-ocr",
                },
            )
            fragment_ids.append(fragment_id)
        await audit.audit_event(
            operation="ingestion",
            record_id=request.document_id,
            correlation=correlation,
            decision="allowed",
            count=len(fragment_ids),
            corpus=request.corpus,
            reason_class="policy",
        )
        return {
            "record_type": "ingestion-result",
            "id": request.document_id,
            "document_id": request.document_id,
            "document_digest": document_digest,
            "fragment_ids": fragment_ids,
            "fragment_count": len(fragment_ids),
        }
    except Exception as exc:
        with suppress(Exception):
            await audit.audit_event(
                operation="ingestion",
                record_id=request.document_id,
                correlation=correlation,
                decision="denied",
                count=0,
                corpus=request.corpus,
                reason_class="validation-or-backend",
            )
        error = CapabilityError(f"{_FAILURE_CLASS}; correlation_id={correlation}")
        raise error from exc


async def ingest_owner_upload(
    operation: Any,
    *,
    store: AsyncStore,
    ocr_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ingest one explicitly selected upload using only server-derived authority."""

    if type(operation) is not dict or not {
        "upload_reference",
        "filename",
        "title",
    } <= set(operation) <= {"upload_reference", "filename", "title", "tags"}:
        raise CapabilityError("Invalid owner upload")
    reference = operation["upload_reference"]
    filename = operation["filename"]
    title = operation["title"]
    tags = operation.get("tags", [])
    if (
        type(reference) is not str
        or len(reference.encode("utf-8")) > 512
        or type(filename) is not str
        or Path(filename).name != filename
        or not filename
        or len(filename.encode("utf-8")) > 255
        or type(title) is not str
        or not title.strip()
        or len(title.encode("utf-8")) > 512
        or type(tags) is not list
        or len(tags) > MAX_DOCUMENT_TAGS
        or any(
            type(tag) is not str
            or not tag.strip()
            or len(tag.encode("utf-8")) > MAX_DOCUMENT_TAG_BYTES
            for tag in tags
        )
    ):
        raise CapabilityError("Invalid owner upload")

    path = approved_document_path(reference, None)
    upload_match = re.fullmatch(r"[0-9a-f]{32}-(.+)", path.name)
    if (
        upload_match is None
        or upload_match.group(1) != filename
        or not any(
            filename.casefold().endswith(extension)
            for extension in supported_extensions()
        )
    ):
        raise CapabilityError("Invalid owner upload")

    source_bytes = path.read_bytes()
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    identity_seed = hashlib.sha256(
        f"owner-upload-v1\n{source_digest}".encode()
    ).hexdigest()
    identity = installation_identity()
    authority = Authority.from_verified_context(
        tenant_id=str(identity["tenant_id"]),
        owner_id=str(identity["owner_id"]),
        principal_id="owner",
        server_verified=True,
    )
    request = DocumentationIngestionRequest(
        requester="owner",
        corpus=CANONICAL_DOCUMENTATION_CORPUS,
        document_id=f"owner-document-{identity_seed}",
        document_ref=reference,
        fragment_id=f"owner-fragment-{identity_seed}",
        operation_id=f"owner-ingestion-{identity_seed}",
        source_type="owner-upload",
        title=title.strip(),
        locator=f"owner-upload:sha256-{source_digest}",
        source_revision=f"sha256-{source_digest}",
        tags=tuple(tags),
        explicitly_selected=True,
        routing_origin="owner-upload-route",
    )

    async def execute_ocr(document_ref: str) -> dict[str, Any]:
        runner = ocr_runner or run_ocr
        result = await asyncio.to_thread(
            runner,
            "Ingest the explicitly selected owner document losslessly.",
            document_ref,
            None,
            "markdown",
        )
        if path.read_bytes() != source_bytes:
            raise CapabilityError("Source changed during OCR")
        return result

    return await supervisor_ingest_document(
        request,
        store=store,
        installation_authority=authority,
        ocr=execute_ocr,
        trusted_requester="owner",
        trusted_routing_origin="owner-upload-route",
        source_approved=True,
    )


async def ingest_public_https(
    operation: Any,
    *,
    store: AsyncStore,
    ocr_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Download and ingest one owner-selected public page through the upload boundary."""

    if type(operation) is not dict or not {"url", "title"} <= set(operation) <= {
        "url",
        "title",
        "tags",
    }:
        raise CapabilityError("Invalid public ingestion")
    url = operation["url"]
    title = operation["title"]
    tags = operation.get("tags", [])
    if (
        type(url) is not str
        or type(title) is not str
        or not title.strip()
        or len(title.encode("utf-8")) > 512
        or type(tags) is not list
        or len(tags) > MAX_DOCUMENT_TAGS
        or any(
            type(tag) is not str
            or not tag.strip()
            or len(tag.encode("utf-8")) > MAX_DOCUMENT_TAG_BYTES
            for tag in tags
        )
    ):
        raise CapabilityError("Invalid public ingestion")

    downloaded = await asyncio.to_thread(download_public_document, url)
    source_digest = hashlib.sha256(downloaded.body).hexdigest()
    filename = f"public-source-{source_digest[:16]}{downloaded.extension}"
    preserved = preserve_ocr_upload(downloaded.body, filename)
    reference = preserved["reference"]
    path = approved_document_path(reference, None)
    if path.read_bytes() != downloaded.body:
        raise CapabilityError("Preserved source mismatch")

    identity = installation_identity()
    authority = Authority.from_verified_context(
        tenant_id=str(identity["tenant_id"]),
        owner_id=str(identity["owner_id"]),
        principal_id="owner",
        server_verified=True,
    )
    request = DocumentationIngestionRequest(
        requester="owner",
        corpus=CANONICAL_DOCUMENTATION_CORPUS,
        document_id=f"public-document-{source_digest}",
        document_ref=reference,
        fragment_id=f"public-fragment-{source_digest}",
        operation_id=f"public-ingestion-{source_digest}",
        source_type=downloaded.source_type,
        title=title.strip(),
        locator=f"public-source:sha256-{source_digest}",
        source_revision=f"sha256-{source_digest}",
        source_uri=downloaded.final_url,
        tags=tuple(tags),
        explicitly_selected=True,
        routing_origin="owner-public-url-route",
    )

    async def execute_ocr(document_ref: str) -> dict[str, Any]:
        runner = ocr_runner or run_ocr
        result = await asyncio.to_thread(
            runner,
            "Ingest the explicitly selected public document losslessly.",
            document_ref,
            None,
            "markdown",
        )
        if path.read_bytes() != downloaded.body:
            raise CapabilityError("Source changed during OCR")
        return result

    return await supervisor_ingest_document(
        request,
        store=store,
        installation_authority=authority,
        ocr=execute_ocr,
        trusted_requester="owner",
        trusted_routing_origin="owner-public-url-route",
        source_approved=True,
    )
