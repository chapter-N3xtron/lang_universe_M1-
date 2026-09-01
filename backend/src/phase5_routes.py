"""Authenticated human-facing Phase 5 routes over the injected Store."""

from __future__ import annotations

from contextlib import suppress
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request
from langgraph.config import get_store

from src.installation_auth import installation_identity
from src.phase5_capabilities import (
    CANONICAL_DOCUMENTATION_CORPUS,
    Authority,
    StoreCapabilities,
)
from src.phase5_ingestion import ingest_owner_upload, ingest_public_https

router = APIRouter(prefix="/phase5", tags=["phase5"])
_LIBRARY_FAILURE = {
    "ok": False,
    "status": "denied",
    "error": "library_read_failed",
    "documents": [],
}
_INGESTION_FAILURE = {
    "ok": False,
    "status": "denied",
    "error": "documentation_ingestion_failed",
}
_DOCUMENT_FIELDS = (
    "record_type",
    "id",
    "corpus",
    "corpus_revision",
    "title",
    "tags",
    "source_uri",
    "source_revision",
    "source_status",
    "source_type",
    "score",
)
_IDENTITY_FIELDS = (
    "identity",
    "tenant_id",
    "trust_domain",
    "owner_type",
    "owner_id",
    "permissions",
    "corpus_grants",
)


def _user_value(user: Any, field: str) -> Any:
    if isinstance(user, dict):
        return user.get(field)
    return getattr(user, field, None)


def installation_authority(request: Request) -> Authority:
    """Require the exact authenticated identity minted by installation auth."""

    expected = installation_identity()
    try:
        user = request.user
    except (AssertionError, RuntimeError):
        user = None
    if user is None or _user_value(user, "is_authenticated") is not True:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if any(_user_value(user, field) != expected[field] for field in _IDENTITY_FIELDS):
        raise HTTPException(status_code=403, detail="Phase 5 request denied.")
    return Authority.from_verified_context(
        tenant_id=str(expected["tenant_id"]),
        owner_id=str(expected["owner_id"]),
        principal_id="owner",
        server_verified=True,
    )


async def read_installation_library(
    operation: Any, *, store: Any, authority: Authority
) -> dict[str, Any]:
    """Execute one bounded library read and return canonical metadata only."""

    if type(operation) is not dict:
        raise ValueError("Invalid library operation")
    api = StoreCapabilities(store, authority)
    kind = operation.get("operation")
    limit = operation.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Invalid library operation")
    records: list[dict[str, Any]] = []
    if kind == "resolve":
        if set(operation) - {"operation", "document_ids", "limit"}:
            raise ValueError("Invalid library operation")
        document_ids = operation.get("document_ids")
        if (
            type(document_ids) is not list
            or not 1 <= len(document_ids) <= 20
            or len(set(document_ids)) != len(document_ids)
            or any(type(document_id) is not str for document_id in document_ids)
        ):
            raise ValueError("Invalid library operation")
        for document_id in document_ids:
            records.extend(
                await api.read_documents(
                    corpus=CANONICAL_DOCUMENTATION_CORPUS,
                    mode="exact",
                    key=document_id,
                    record_type="document",
                    limit=1,
                )
            )
        order = {document_id: index for index, document_id in enumerate(document_ids)}
        records.sort(key=lambda row: order.get(row.get("id"), len(order)))
    elif kind == "metadata":
        if set(operation) - {"operation", "filters", "limit"}:
            raise ValueError("Invalid library operation")
        records = await api.read_documents(
            corpus=CANONICAL_DOCUMENTATION_CORPUS,
            mode="metadata",
            filters=operation.get("filters"),
            limit=limit,
            record_type="document",
        )
    elif kind == "semantic":
        if set(operation) - {"operation", "query", "filters", "limit"}:
            raise ValueError("Invalid library operation")
        filters = operation.get("filters") or {}
        if type(filters) is not dict or set(filters) - {
            "tag",
            "source_type",
            "source_revision",
        }:
            raise ValueError("Invalid library operation")
        if any(
            type(value) is not str or not value or len(value.encode("utf-8")) > 1024
            for value in filters.values()
        ):
            raise ValueError("Invalid library operation")
        fragments = await api.read_documents(
            corpus=CANONICAL_DOCUMENTATION_CORPUS,
            mode="semantic",
            query=operation.get("query", ""),
            limit=20,
        )
        seen: set[str] = set()
        for fragment in fragments:
            document_id = fragment.get("document_id")
            if type(document_id) is not str or document_id in seen:
                continue
            if any(
                (
                    " ".join(str(value).casefold().split())
                    not in fragment.get("tags", [])
                    if name == "tag"
                    else fragment.get(name) != value
                )
                for name, value in filters.items()
            ):
                continue
            seen.add(document_id)
            records.append(fragment | {"id": document_id})
            if len(records) >= limit:
                break
    else:
        raise ValueError("Invalid library operation")

    documents = [
        {field: row[field] for field in _DOCUMENT_FIELDS if field in row}
        for row in records[:limit]
        if row.get("source_status") == "active"
    ]
    return {
        "ok": True,
        "status": "complete",
        "operation": kind,
        "documents": documents,
    }


@router.post("/installation-library")
async def installation_library_route(
    request: Request, operation: Annotated[Any, Body()]
) -> dict[str, Any]:
    authority = installation_authority(request)
    store = get_store()
    try:
        return await read_installation_library(
            operation, store=store, authority=authority
        )
    except Exception:
        with suppress(Exception):
            await StoreCapabilities(store, authority).audit_event(
                operation="documentation-read",
                record_id="manual-library",
                correlation="route-denial",
                decision="denied",
                count=0,
                corpus=CANONICAL_DOCUMENTATION_CORPUS,
                reason_class="validation-or-backend",
            )
        return dict(_LIBRARY_FAILURE)


@router.post("/public-document")
async def public_document_route(
    request: Request, operation: Annotated[Any, Body()]
) -> dict[str, Any]:
    authority = installation_authority(request)
    store = get_store()
    try:
        result = await ingest_public_https(operation, store=store)
        return {
            "ok": True,
            "status": "complete",
            "document_id": result["document_id"],
            "fragment_count": result["fragment_count"],
        }
    except Exception:
        with suppress(Exception):
            await StoreCapabilities(store, authority).audit_event(
                operation="ingestion",
                record_id="manual-public-document",
                correlation="route-denial",
                decision="denied",
                count=0,
                corpus=CANONICAL_DOCUMENTATION_CORPUS,
                reason_class="validation-or-backend",
            )
        return dict(_INGESTION_FAILURE)


@router.post("/owner-upload")
async def owner_upload_route(
    request: Request, operation: Annotated[Any, Body()]
) -> dict[str, Any]:
    authority = installation_authority(request)
    store = get_store()
    try:
        result = await ingest_owner_upload(operation, store=store)
        return {
            "ok": True,
            "status": "complete",
            "document_id": result["document_id"],
            "fragment_count": result["fragment_count"],
        }
    except Exception:
        with suppress(Exception):
            await StoreCapabilities(store, authority).audit_event(
                operation="ingestion",
                record_id="manual-owner-upload",
                correlation="route-denial",
                decision="denied",
                count=0,
                corpus=CANONICAL_DOCUMENTATION_CORPUS,
                reason_class="validation-or-backend",
            )
        return dict(_INGESTION_FAILURE)
