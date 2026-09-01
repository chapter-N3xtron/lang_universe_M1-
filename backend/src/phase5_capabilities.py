r"""Phase 5 trusted capabilities over the Agent Server-injected BaseStore.

Documentation content retrieval delegates semantic ranking to the configured Store
index. Memory lexical matching remains deliberately non-semantic: Unicode text is
NFKC/casefolded, words are ``\w+`` tokens, score is the number of distinct query
tokens present, and ties are ordered by record id. Memory has one current item per
ID. Ordinary Store writes are last-write-wins; no CAS or multi-key transaction is
assumed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from langgraph.store.base import Item


@runtime_checkable
class AsyncStore(Protocol):
    """The internal subset of LangGraph BaseStore used by Phase 5."""

    async def aget(self, namespace: tuple[str, ...], key: str) -> Item | None: ...

    async def aput(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
        *,
        index: bool | Sequence[str] | None = None,
        ttl: float | None = None,
    ) -> None: ...

    async def adelete(self, namespace: tuple[str, ...], key: str) -> None: ...

    async def asearch(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        filter: dict[str, Any] | None = None,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Item]: ...


MEMORY_KINDS = frozenset(
    {
        "user preferences",
        "user-provided facts",
        "project decisions",
        "task outcomes",
        "reusable instructions",
    }
)
MEMORY_OPERATIONS = frozenset(
    {"read", "write", "delete", "restore", "permanent-delete", "audit"}
)
MAX_KIND_BYTES = 15 * 1024 * 1024
MAX_ITEM_BYTES = 32 * 1024
MAX_METADATA_BYTES = 8 * 1024
MAX_METADATA_FIELDS = 32
MAX_QUERY_BYTES = 4 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_BATCH = 10
MAX_CANDIDATES = 1000
_CAPACITY_PAGE_SIZE = 1000
MAX_RESULTS = 20
MAX_FILTERS = 8
CANONICAL_DOCUMENTATION_CORPUS = "installation-docs"
MAX_DOCUMENT_TAGS = 32
MAX_DOCUMENT_TAG_BYTES = 128
_PHASE5_AUDIT_OPERATIONS = frozenset(
    {
        "read",
        "write",
        "delete",
        "restore",
        "permanent-delete",
        "audit",
        "documentation-read",
        "documentation-write",
        "ingestion",
    }
)
_PHASE5_AUDIT_DECISIONS = frozenset({"allowed", "denied"})
_PHASE5_REASON_CLASSES = frozenset({"policy", "validation-or-backend", "tool-denial"})
MAX_FILTER_VALUE_BYTES = 1024
RESTORE_WINDOW = timedelta(days=7)
AUDIT_RETENTION = timedelta(days=90)
# Native expiration is best-effort and sweeps asynchronously. One configured sweep
# interval of padding preserves the inclusive logical boundary; reads enforce the
# exact policy cutoff even while an expired item awaits physical deletion.
TTL_SWEEP_INTERVAL_MINUTES = 60
DELETED_MEMORY_TTL_MINUTES = (
    RESTORE_WINDOW.total_seconds() / 60 + TTL_SWEEP_INTERVAL_MINUTES
)
AUDIT_TTL_MINUTES = AUDIT_RETENTION.total_seconds() / 60 + TTL_SWEEP_INTERVAL_MINUTES
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WORD = re.compile(r"\w+", re.UNICODE)
PROHIBITED_CONTENT_CLASSES = frozenset(
    {"credentials", "authorization-header", "private-key", "internal-reasoning"}
)
_OBVIOUS_SECRET_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "private_key",
        "client_secret",
        "access_token",
        "refresh_token",
        "auth_header",
        "credential",
        "credentials",
    }
)
DOC_SOURCE_TYPES = frozenset(
    {
        "public-https",
        "public-pdf",
        "owner-upload",
        "approved-private-workspace",
        "coder-report",
    }
)
DOC_ACTIVE = frozenset({"active"})
DOC_INACTIVE = frozenset(
    {
        "deleted",
        "expired",
        "quarantined",
        "superseded-withdrawn",
        "withdrawn",
        "revoked",
        "unavailable",
    }
)


class CapabilityError(ValueError):
    """A fail-closed, sanitized contract rejection."""


@dataclass(frozen=True)
class _MemoryWritePlan:
    kind: str
    memory_id: str
    envelope: dict[str, Any]
    create: bool


@dataclass(frozen=True)
class Delegation:
    issuer: str
    subject: str
    operations: frozenset[str]
    corpora: frozenset[str] = frozenset()
    expires_at: datetime | None = None
    supervisor_created: bool = False

    def permits(self, operation: str, corpus: str | None, now: datetime) -> bool:
        return (
            operation in self.operations
            and (corpus is None or corpus in self.corpora)
            and (self.expires_at is None or now <= self.expires_at)
            and (
                operation != "documentation-retrieval:write" or self.supervisor_created
            )
        )


@dataclass(frozen=True)
class Authority:
    tenant_id: str
    owner_id: str
    trust_domain: str = "local-installation-v1"
    owner_type: str = "person"
    principal_id: str = "owner"
    memory_grants: frozenset[str] = frozenset()
    corpus_read_grants: frozenset[str] = frozenset()
    delegation: Delegation | None = None

    @classmethod
    def from_verified_context(
        cls,
        *,
        tenant_id: str,
        owner_id: str,
        principal_id: str,
        server_verified: bool,
        delegated_memory: frozenset[str] = frozenset(),
        delegated_corpora: frozenset[str] = frozenset(),
    ) -> Authority:
        """Create authority only from an authenticated graph/server identity."""
        if not server_verified:
            raise CapabilityError("Verified graph identity required")
        principal = principal_id.casefold()
        if principal in {"owner", owner_id.casefold()}:
            memory = MEMORY_OPERATIONS
            corpora = delegated_corpora or frozenset({CANONICAL_DOCUMENTATION_CORPUS})
            principal_id = "owner"
        elif principal in {"jasper", "coder", "librarian"}:
            allowed = frozenset({"read", "write", "delete"})
            if not delegated_memory <= allowed:
                raise CapabilityError("Unsupported specialist delegation")
            memory, corpora = delegated_memory, delegated_corpora
        elif principal == "ocr":
            if delegated_memory:
                raise CapabilityError("OCR cannot receive memory grants")
            memory, corpora = frozenset(), delegated_corpora
        else:
            raise CapabilityError("Unknown principal")
        return cls(
            tenant_id,
            owner_id,
            principal_id=principal_id,
            memory_grants=memory,
            corpus_read_grants=corpora,
        )

    def __post_init__(self) -> None:
        for value in (
            self.tenant_id,
            self.owner_id,
            self.trust_domain,
            self.principal_id,
        ):
            _identifier(value, "authority identifier")
        if self.owner_type != "person" or self.trust_domain != "local-installation-v1":
            raise CapabilityError("Unsupported authority")
        if not self.memory_grants <= MEMORY_OPERATIONS:
            raise CapabilityError("Unsupported memory grant")
        if self.principal_id.lower() == "ocr" and self.memory_grants:
            raise CapabilityError("OCR cannot receive memory grants")
        for corpus in self.corpus_read_grants:
            _identifier(corpus, "corpus grant")
        if not self.corpus_read_grants <= {CANONICAL_DOCUMENTATION_CORPUS}:
            raise CapabilityError("Unsupported corpus grant")
        if self.delegation and not self.delegation.corpora <= {
            CANONICAL_DOCUMENTATION_CORPUS
        }:
            raise CapabilityError("Unsupported corpus delegation")


def _identifier(value: Any, label: str = "identifier") -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise CapabilityError(f"Invalid {label}")
    return value


def memory_namespace(auth: Authority, kind: str) -> tuple[str, ...]:
    """Return the sole server-derived namespace for current items of one kind."""
    if type(kind) is not str or kind not in MEMORY_KINDS:
        raise CapabilityError("Unsupported memory kind")
    return (
        "app",
        "v1",
        "cross-session-memory",
        f"tenant:{auth.tenant_id}",
        f"trust:{auth.trust_domain}",
        f"owner:person:{auth.owner_id}",
        f"kind:{kind.replace(' ', '-')}",
    )


def documentation_namespace(
    auth: Authority, corpus: str, record: str = "fragment"
) -> tuple[str, ...]:
    if corpus != CANONICAL_DOCUMENTATION_CORPUS:
        raise CapabilityError("Invalid documentation corpus")
    if record not in {"fragment", "document"}:
        raise CapabilityError("Invalid documentation scope")
    return (
        "app",
        "v1",
        "documentation-retrieval",
        f"tenant:{auth.tenant_id}",
        f"trust:{auth.trust_domain}",
        f"owner:person:{auth.owner_id}",
        f"corpus:{corpus}",
        f"record:{record}",
    )


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CapabilityError("Value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _value(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    value = item.get("value", {}) if isinstance(item, dict) else item.value
    return dict(value) if isinstance(value, dict) else {}


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(unicodedata.normalize("NFKC", text).casefold()))


def _query(query: Any) -> str:
    if type(query) is not str or len(query.encode("utf-8")) > MAX_QUERY_BYTES:
        raise CapabilityError("Invalid query")
    return query


def lexical_rank(query: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _query(query)
    if type(records) is not list or len(records) > MAX_CANDIDATES:
        raise CapabilityError("Authorized candidate bound exceeded")
    words = _tokens(query)
    ranked = [
        (len(words & _tokens(str(row.get("content", "")))), str(row.get("id", "")), row)
        for row in records
    ]
    return [
        row
        for score, _, row in sorted(ranked, key=lambda part: (-part[0], part[1]))
        if score
    ]


def _validate_string_map(value: Any, *, metadata: bool = False) -> dict[str, str]:
    if type(value) is not dict or (metadata and len(value) > MAX_METADATA_FIELDS):
        raise CapabilityError("Invalid metadata")
    for key, item in value.items():
        if (
            type(key) is not str
            or type(item) is not str
            or not key
            or len(key.encode()) > 128
            or len(item.encode()) > MAX_FILTER_VALUE_BYTES
        ):
            raise CapabilityError("Metadata fields must be bounded strings")
        if key.casefold() in _OBVIOUS_SECRET_FIELDS:
            raise CapabilityError("Obvious credential fields are prohibited")
    if metadata and len(_canonical(value)) > MAX_METADATA_BYTES:
        raise CapabilityError("Metadata exceeds bounds")
    return value


def _document_tags(value: Any) -> list[str]:
    if type(value) not in {list, tuple} or len(value) > MAX_DOCUMENT_TAGS:
        raise CapabilityError("Invalid document tags")
    normalized: set[str] = set()
    for tag in value:
        if type(tag) is not str:
            raise CapabilityError("Invalid document tags")
        clean = " ".join(unicodedata.normalize("NFKC", tag).casefold().split())
        if not clean or len(clean.encode("utf-8")) > MAX_DOCUMENT_TAG_BYTES:
            raise CapabilityError("Invalid document tags")
        normalized.add(clean)
    tags = sorted(normalized)
    if len(_canonical(tags)) > MAX_METADATA_BYTES:
        raise CapabilityError("Document tags exceed bounds")
    return tags


def _validate_content(content: Any, content_class: Any) -> str:
    if (
        type(content) is not str
        or not content
        or len(content.encode("utf-8")) > MAX_ITEM_BYTES
    ):
        raise CapabilityError("Invalid content")
    if (
        type(content_class) is not str
        or content_class in PROHIBITED_CONTENT_CLASSES
        or content_class not in {"ordinary", "documentation"}
    ):
        raise CapabilityError("Prohibited or unknown content class")
    # This is intentionally conservative and finite, not a claim of arbitrary secret detection.
    if (
        "-----BEGIN " in content
        and "PRIVATE KEY-----" in content
        or re.search(r"(?im)^authorization\s*:\s*(?:bearer|basic)\s+\S+", content)
    ):
        raise CapabilityError("Obvious credential material is prohibited")
    return content


class StoreCapabilities:
    def __init__(
        self, store: Any, authority: Authority, *, now=lambda: datetime.now(UTC)
    ) -> None:
        self.store, self.authority, self.now = store, authority, now

    def _permit(self, operation: str, corpus: str | None = None) -> None:
        if operation.startswith("documentation-retrieval:"):
            if type(corpus) is not str:
                raise CapabilityError("Capability denied")
            if (
                operation == "documentation-retrieval:read"
                and corpus in self.authority.corpus_read_grants
            ):
                return
            delegation = self.authority.delegation
            if delegation and delegation.permits(operation, corpus, self.now()):
                return
        elif operation in self.authority.memory_grants:
            return
        raise CapabilityError("Capability denied")

    async def _search(
        self,
        namespace: tuple[str, ...],
        *,
        limit: int = MAX_CANDIDATES,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
            raise CapabilityError("Candidate bound exceeded")
        if query is None:
            result = await self.store.asearch(namespace, limit=limit, offset=0)
        else:
            result = await self.store.asearch(
                namespace, query=query, limit=limit, offset=0
            )
        if len(result) > limit:
            raise CapabilityError("Store exceeded candidate bound")
        rows = []
        for item in result:
            row = {
                "_key": str(
                    item.get("key", item.get("id", ""))
                    if isinstance(item, dict)
                    else item.key
                ),
                **_value(item),
            }
            if query is not None:
                row["score"] = (
                    item.get("score") if isinstance(item, dict) else item.score
                )
            rows.append(row)
        return rows

    async def _memory(
        self, namespace: tuple[str, ...], memory_id: str
    ) -> dict[str, Any] | None:
        item = await self.store.aget(namespace, memory_id)
        if item is None:
            return None
        return {"_key": memory_id, **_value(item)}

    async def _memories(self, namespace: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        rows = await self._search(namespace)
        return {
            str(row["id"]): row
            for row in rows
            if row.get("record_type") == "memory" and row.get("id")
        }

    async def _validated_write_plan(
        self,
        *,
        kind: str,
        content: str,
        metadata: dict[str, str],
        provenance: dict[str, str],
        operation_id: str,
        content_class: str,
        timestamp: str,
    ) -> _MemoryWritePlan:
        """Validate fully, then inspect the one deterministic item for a retry."""
        self._permit("write")
        namespace = memory_namespace(self.authority, kind)
        _validate_content(content, content_class)
        _validate_string_map(metadata, metadata=True)
        _validate_string_map(provenance)
        if not {"source_type", "source_id", "actor"} <= set(provenance):
            raise CapabilityError("Incomplete memory provenance")
        provenance = {
            "source_time": "unknown",
            **provenance,
            "creation_method": "explicit-authorized-write",
        }
        _validate_string_map(provenance)
        _identifier(operation_id, "operation id")
        request = {
            "kind": kind,
            "content": content,
            "content_class": content_class,
            "metadata": metadata,
            "provenance": provenance,
        }
        request_digest = _digest(request)
        memory_id = hashlib.sha256(
            f"{self.authority.owner_id}:{kind}:{operation_id}".encode()
        ).hexdigest()
        current = await self._memory(namespace, memory_id)
        if current:
            if current.get("request_digest") != request_digest:
                raise CapabilityError("Idempotency key conflict")
            return _MemoryWritePlan(
                kind,
                memory_id,
                {key: value for key, value in current.items() if key != "_key"},
                False,
            )
        envelope = {
            "schema_version": 1,
            "record_type": "memory",
            "id": memory_id,
            **request,
            "request_digest": request_digest,
            "tenant_id": self.authority.tenant_id,
            "trust_domain": self.authority.trust_domain,
            "owner_type": "person",
            "owner_id": self.authority.owner_id,
            "created_at": timestamp,
            "updated_at": timestamp,
            "lifecycle_state": "active",
            "revision": 1,
            "operation_id": operation_id,
            "deleted_at": None,
        }
        return _MemoryWritePlan(kind, memory_id, envelope, True)

    async def _check_write_capacity(self, plans: list[_MemoryWritePlan]) -> None:
        additions: dict[str, int] = {}
        for plan in plans:
            if plan.create:
                additions[plan.kind] = additions.get(plan.kind, 0) + len(
                    _canonical(plan.envelope)
                )
        for kind, addition in additions.items():
            if addition > MAX_KIND_BYTES:
                raise CapabilityError(
                    "Memory kind capacity exceeded; no eviction performed"
                )
            namespace = memory_namespace(self.authority, kind)
            seen: set[str] = set()
            used = 0
            offset = 0
            while True:
                page = await self.store.asearch(
                    namespace, limit=_CAPACITY_PAGE_SIZE, offset=offset
                )
                if len(page) > _CAPACITY_PAGE_SIZE:
                    raise CapabilityError("Store exceeded capacity page bound")
                for item in page:
                    key = str(
                        item.get("key", item.get("id", ""))
                        if isinstance(item, dict)
                        else item.key
                    )
                    if not key:
                        raise CapabilityError("Memory capacity accounting failed")
                    if key in seen:
                        continue
                    seen.add(key)
                    used += len(_canonical(_value(item)))
                    if used + addition > MAX_KIND_BYTES:
                        raise CapabilityError(
                            "Memory kind capacity exceeded; no eviction performed"
                        )
                if len(page) < _CAPACITY_PAGE_SIZE:
                    break
                offset += len(page)

    async def _execute_write_plan(self, plan: _MemoryWritePlan) -> dict[str, Any]:
        if plan.create:
            await self.store.aput(
                memory_namespace(self.authority, plan.kind),
                plan.memory_id,
                plan.envelope,
                index=False,
                ttl=None,
            )
            await self._audit(
                "write", plan.memory_id, plan.envelope["operation_id"], "allowed", 1
            )
        return plan.envelope

    async def write_memory(
        self,
        *,
        kind: str,
        content: str,
        metadata: dict[str, str],
        provenance: dict[str, str],
        operation_id: str,
        content_class: str = "ordinary",
    ) -> dict[str, Any]:
        plan = await self._validated_write_plan(
            kind=kind,
            content=content,
            metadata=metadata,
            provenance=provenance,
            operation_id=operation_id,
            content_class=content_class,
            timestamp=self.now().isoformat(),
        )
        await self._check_write_capacity([plan])
        return await self._execute_write_plan(plan)

    async def write_memory_batch(
        self, writes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if type(writes) is not list or not 1 <= len(writes) <= MAX_BATCH:
            raise CapabilityError("Invalid write batch")
        self._permit("write")
        allowed = {
            "kind",
            "content",
            "metadata",
            "provenance",
            "operation_id",
            "content_class",
        }
        required = {"kind", "content", "metadata", "provenance", "operation_id"}
        seen: set[str] = set()
        timestamp = self.now().isoformat()
        plans: list[_MemoryWritePlan] = []
        for item in writes:
            if (
                type(item) is not dict
                or set(item) - allowed
                or not required <= set(item)
            ):
                raise CapabilityError("Invalid write batch item")
            operation = str(item["operation_id"])
            if operation in seen:
                raise CapabilityError("Duplicate operation id")
            seen.add(operation)
            plans.append(
                await self._validated_write_plan(
                    kind=item["kind"],
                    content=item["content"],
                    metadata=item["metadata"],
                    provenance=item["provenance"],
                    operation_id=item["operation_id"],
                    content_class=item.get("content_class", "ordinary"),
                    timestamp=timestamp,
                )
            )
        await self._check_write_capacity(plans)
        return [await self._execute_write_plan(plan) for plan in plans]

    def _filters(self, filters: Any, allowed: set[str]) -> dict[str, str]:
        filters = _validate_string_map(filters or {})
        if not filters or len(filters) > MAX_FILTERS or not set(filters) <= allowed:
            raise CapabilityError("Unsupported metadata filter")
        return filters

    async def read_memory(
        self,
        *,
        kind: str,
        mode: str,
        key: str = "",
        query: str = "",
        filters: dict[str, str] | None = None,
        limit: int = MAX_RESULTS,
    ) -> list[dict[str, Any]]:
        self._permit("read")
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise CapabilityError("Invalid result bound")
        namespace = memory_namespace(self.authority, kind)
        selected: dict[str, str] | None = None
        normalized_query: str | None = None
        if mode == "exact":
            _identifier(key, "memory id")
        elif mode == "metadata":
            selected = self._filters(filters, {"source_type", "source_id"})
        elif mode == "lexical":
            normalized_query = _query(query)
        else:
            raise CapabilityError("Unsupported match mode")

        if mode == "exact":
            memory = await self._memory(namespace, key)
            rows = [memory] if memory is not None else []
        else:
            rows = list((await self._memories(namespace)).values())
        rows = [
            r
            for r in rows
            if not r.get("deleted_at")
            and not r.get("purged_at")
            and r.get("lifecycle_state", "active") == "active"
        ]
        if mode == "metadata":
            assert selected is not None
            rows = [
                r
                for r in rows
                if all(r.get("provenance", {}).get(k) == v for k, v in selected.items())
            ]
            rows.sort(key=lambda row: str(row["id"]))
        elif mode == "lexical":
            assert normalized_query is not None
            rows = lexical_rank(normalized_query, rows)
        result = [
            {k: v for k, v in row.items() if k != "_key"} | {"match_mode": mode}
            for row in rows[:limit]
        ]
        self._response(result)
        await self._audit(
            "read", key or "multiple", "read", "allowed", len(result), match_mode=mode
        )
        return result

    async def delete_memory(
        self,
        kind: str,
        memory_id: str,
        operation_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._lifecycle(
            kind, memory_id, operation_id, "delete", expected_revision
        )

    async def restore_memory(
        self,
        kind: str,
        memory_id: str,
        operation_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._lifecycle(
            kind, memory_id, operation_id, "restore", expected_revision
        )

    async def purge_memory(
        self,
        kind: str,
        memory_id: str,
        operation_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return await self._lifecycle(
            kind, memory_id, operation_id, "permanent-delete", expected_revision
        )

    async def _lifecycle(
        self,
        kind: str,
        memory_id: str,
        operation_id: str,
        action: str,
        expected_revision: int | None,
    ) -> dict[str, Any]:
        self._permit(action)
        if action in {
            "restore",
            "permanent-delete",
        } and self.authority.principal_id not in {
            "owner",
            self.authority.owner_id,
        }:
            raise CapabilityError("Owner-only lifecycle access denied")
        _identifier(memory_id, "memory id")
        _identifier(operation_id, "operation id")
        namespace = memory_namespace(self.authority, kind)
        row = await self._memory(namespace, memory_id)
        if not row:
            raise CapabilityError("Memory not found")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision != row["revision"]
        ):
            raise CapabilityError("Stale memory revision")
        now = self.now()
        deleted = (
            datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None
        )
        if action == "delete" and deleted:
            return {key: value for key, value in row.items() if key != "_key"}
        if action == "restore" and (not deleted or now > deleted + RESTORE_WINDOW):
            raise CapabilityError("Memory is not restorable")
        if action == "permanent-delete" and not deleted:
            raise CapabilityError("Permanent delete requires an exact deleted memory")

        if action == "permanent-delete":
            await self.store.adelete(namespace, memory_id)
            await self._audit(action, memory_id, operation_id, "allowed", 1)
            return {"id": memory_id, "purged": True}

        changes = (
            {"deleted_at": now.isoformat(), "lifecycle_state": "deleted"}
            if action == "delete"
            else {"deleted_at": None, "lifecycle_state": "active"}
        )
        updated = (
            {key: value for key, value in row.items() if key != "_key"}
            | changes
            | {
                "revision": int(row["revision"]) + 1,
                "updated_at": now.isoformat(),
                "operation_id": operation_id,
            }
        )
        await self.store.aput(
            namespace,
            memory_id,
            updated,
            index=False,
            ttl=DELETED_MEMORY_TTL_MINUTES if action == "delete" else None,
        )
        await self._audit(action, memory_id, operation_id, "allowed", 1)
        return updated

    async def _document_record(
        self, corpus: str, document_id: str
    ) -> dict[str, Any] | None:
        item = await self.store.aget(
            documentation_namespace(self.authority, corpus, "document"), document_id
        )
        return {"_key": document_id, **_value(item)} if item is not None else None

    async def _fragment_record(
        self, corpus: str, fragment_id: str
    ) -> dict[str, Any] | None:
        item = await self.store.aget(
            documentation_namespace(self.authority, corpus, "fragment"), fragment_id
        )
        return {"_key": fragment_id, **_value(item)} if item is not None else None

    def _active_document(self, row: dict[str, Any]) -> bool:
        status = row.get(
            "source_status", row.get("provenance", {}).get("source_status")
        )
        if status not in DOC_ACTIVE | DOC_INACTIVE:
            raise CapabilityError("Documentation lifecycle verification failed")
        return status in DOC_ACTIVE

    def _document_result(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "_key"}

    def _fragment_result(
        self, fragment: dict[str, Any], document: dict[str, Any]
    ) -> dict[str, Any]:
        # Document metadata is stored only in the canonical document item. It is joined
        # into the bounded response after authorization; the fragment never owns it.
        canonical = self._document_result(document)
        canonical.pop("id", None)
        canonical.pop("record_type", None)
        canonical.pop("created_at", None)
        canonical.pop("metadata_digest", None)
        return {
            key: value for key, value in fragment.items() if key != "_key"
        } | canonical

    async def write_document(
        self,
        *,
        corpus: str,
        fragment_id: str,
        content: str,
        provenance: dict[str, str],
        operation_id: str,
        supervisor_approved: bool = False,
        ocr_succeeded: bool = False,
        content_class: str = "documentation",
        corpus_revision: str = "1",
        tags: list[str] | tuple[str, ...] = (),
    ) -> dict[str, Any]:
        self._permit("documentation-retrieval:write", corpus)
        if not supervisor_approved or not ocr_succeeded:
            raise CapabilityError("Documentation write denied")
        # The namespace constructor also fixes the sole installation-wide corpus before
        # any Store access. All request validation below completes before mutation.
        document_namespace = documentation_namespace(self.authority, corpus, "document")
        fragment_namespace = documentation_namespace(self.authority, corpus, "fragment")
        _identifier(fragment_id, "fragment id")
        _identifier(operation_id, "operation id")
        _identifier(corpus_revision, "corpus revision")
        _validate_content(content, content_class)
        _validate_string_map(provenance, metadata=True)
        canonical_tags = _document_tags(tags)
        required = {
            "document_id",
            "locator",
            "title",
            "source_revision",
            "digest",
            "source_status",
            "source_type",
        }
        allowed = required | {
            "document_digest",
            "fragment_index",
            "fragment_count",
            "char_start",
            "char_end",
            "source_uri",
            "source_time",
            "requester",
            "routing_origin",
            "routing_exit",
            "ocr_authority",
            "supervisor_stage",
        }
        if (
            set(provenance) - allowed
            or not required <= set(provenance)
            or provenance["source_type"] not in DOC_SOURCE_TYPES
            or provenance["source_status"] not in DOC_ACTIVE | DOC_INACTIVE
        ):
            raise CapabilityError("Unapproved or incomplete documentation source")
        document_id = _identifier(provenance["document_id"], "document id")
        if document_id == fragment_id:
            raise CapabilityError("Document and fragment identities must be distinct")

        now = self.now().isoformat()
        document_digest = provenance.get("document_digest", provenance["digest"])
        canonical_provenance = {
            key: value
            for key, value in provenance.items()
            if key
            not in {
                "locator",
                "digest",
                "document_digest",
                "fragment_index",
                "fragment_count",
                "char_start",
                "char_end",
            }
        }
        document_metadata = {
            "schema_version": 1,
            "record_type": "document",
            "id": document_id,
            "corpus": corpus,
            "corpus_revision": corpus_revision,
            "title": provenance["title"],
            "tags": canonical_tags,
            "source_uri": provenance.get("source_uri", "unknown"),
            "source_revision": provenance["source_revision"],
            "digest": document_digest,
            "source_time": provenance.get("source_time", "unknown"),
            "source_status": provenance["source_status"],
            "source_type": provenance["source_type"],
            "provenance": canonical_provenance,
            "created_at": now,
            "untrusted_data": True,
        }
        metadata_digest = _digest(
            {
                key: value
                for key, value in document_metadata.items()
                if key != "created_at"
            }
        )
        document_metadata["metadata_digest"] = metadata_digest
        if len(_canonical(document_metadata)) > MAX_METADATA_BYTES:
            raise CapabilityError("Document metadata exceeds bounds")
        request_digest = _digest(
            {
                "corpus": corpus,
                "fragment_id": fragment_id,
                "content": content,
                "document_metadata_digest": metadata_digest,
                "locator": provenance["locator"],
            }
        )
        fragment = {
            "schema_version": 1,
            "record_type": "fragment",
            "id": fragment_id,
            "content": content,
            "corpus": corpus,
            "corpus_revision": corpus_revision,
            "document_id": document_id,
            "fragment_id": fragment_id,
            "locator": provenance["locator"],
            "fragment_index": provenance.get("fragment_index", "0"),
            "fragment_count": provenance.get("fragment_count", "1"),
            "char_start": provenance.get("char_start", "0"),
            "char_end": provenance.get("char_end", str(len(content))),
            "digest": provenance["digest"],
            "request_digest": request_digest,
            "operation_id": operation_id,
            "created_at": now,
            "untrusted_data": True,
        }

        existing_document = await self._document_record(corpus, document_id)
        existing_fragment = await self._fragment_record(corpus, fragment_id)
        if (
            existing_document
            and existing_document.get("metadata_digest") != metadata_digest
        ):
            raise CapabilityError("Immutable canonical document already exists")
        if (
            existing_fragment
            and existing_fragment.get("request_digest") != request_digest
        ):
            raise CapabilityError("Immutable documentation fragment already exists")
        if existing_fragment:
            if not existing_document:
                raise CapabilityError("Canonical document metadata is unavailable")
            return self._fragment_result(existing_fragment, existing_document)

        # BaseStore has no multi-key transaction. The validated canonical metadata is
        # written first when absent, followed by the one fragment; no atomicity claim,
        # lock, rollback protocol, operation record, or content copy is introduced.
        if not existing_document:
            await self.store.aput(
                document_namespace, document_id, document_metadata, index=False
            )
            existing_document = {"_key": document_id, **document_metadata}
        await self.store.aput(
            fragment_namespace, fragment_id, fragment, index=["content"]
        )
        await self._audit(
            "documentation-write",
            fragment_id,
            operation_id,
            "allowed",
            1,
            corpus=corpus,
        )
        return self._fragment_result(fragment, existing_document)

    async def update_document_tags(
        self,
        *,
        corpus: str,
        document_id: str,
        tags: list[str] | tuple[str, ...],
        operation_id: str,
    ) -> dict[str, Any]:
        """Replace only canonical document tags through delegated write authority."""

        self._permit("documentation-retrieval:write", corpus)
        _identifier(document_id, "document id")
        _identifier(operation_id, "operation id")
        canonical_tags = _document_tags(tags)
        row = await self._document_record(corpus, document_id)
        if row is None or not self._active_document(row):
            raise CapabilityError("Canonical document metadata is unavailable")
        updated = {
            key: value
            for key, value in row.items()
            if key not in {"_key", "metadata_digest"}
        }
        updated["tags"] = canonical_tags
        updated["metadata_digest"] = _digest(
            {key: value for key, value in updated.items() if key != "created_at"}
        )
        if len(_canonical(updated)) > MAX_METADATA_BYTES:
            raise CapabilityError("Document metadata exceeds bounds")
        await self.store.aput(
            documentation_namespace(self.authority, corpus, "document"),
            document_id,
            updated,
            index=False,
        )
        await self._audit(
            "documentation-write",
            document_id,
            operation_id,
            "allowed",
            1,
            corpus=corpus,
        )
        return updated

    async def read_documents(
        self,
        *,
        corpus: str,
        mode: str,
        key: str = "",
        query: str = "",
        filters: dict[str, str] | None = None,
        limit: int = MAX_RESULTS,
        corpus_revision: str | None = None,
        record_type: str = "fragment",
    ) -> list[dict[str, Any]]:
        self._permit("documentation-retrieval:read", corpus)
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise CapabilityError("Invalid result bound")
        document_namespace = documentation_namespace(self.authority, corpus, "document")
        fragment_namespace = documentation_namespace(self.authority, corpus, "fragment")
        if corpus_revision is not None:
            _identifier(corpus_revision, "corpus revision")
        selected: dict[str, str] | None = None
        semantic_query: str | None = None
        if mode == "exact":
            _identifier(key, "document or fragment id")
            if record_type not in {"document", "fragment"}:
                raise CapabilityError("Invalid exact record type")
        elif mode == "metadata":
            selected = (
                {}
                if filters is None or filters == {}
                else self._filters(
                    filters,
                    {
                        "document_id",
                        "tag",
                        "source_type",
                        "source_revision",
                        "source_status",
                    },
                )
            )
        elif mode == "semantic":
            semantic_query = _query(query)
        else:
            raise CapabilityError("Unsupported match mode")

        rows: list[dict[str, Any]] = []
        if mode == "exact" and record_type == "document":
            document = await self._document_record(corpus, key)
            if document is not None and self._active_document(document):
                rows = [self._document_result(document)]
        elif mode == "exact":
            fragment = await self._fragment_record(corpus, key)
            if fragment is not None:
                document = await self._document_record(
                    corpus, str(fragment.get("document_id", ""))
                )
                if document is None:
                    raise CapabilityError("Documentation lifecycle verification failed")
                if self._active_document(document):
                    rows = [self._fragment_result(fragment, document)]
        elif mode == "metadata":
            documents = await self._search(document_namespace)
            for document in documents:
                if document.get("record_type") != "document":
                    continue
                if not self._active_document(document):
                    continue
                rows.append(self._document_result(document))
        else:
            # The configured Store index embeds only fragment content. Supplying the
            # query delegates semantic ranking to BaseStore while retaining the fully
            # authorized namespace and hard candidate bound.
            assert semantic_query is not None
            fragments = await self._search(fragment_namespace, query=semantic_query)
            for fragment in fragments:
                if fragment.get("record_type") != "fragment":
                    continue
                document = await self._document_record(
                    corpus, str(fragment.get("document_id", ""))
                )
                if document is None:
                    raise CapabilityError("Documentation lifecycle verification failed")
                if self._active_document(document):
                    rows.append(self._fragment_result(fragment, document))

        if selected is not None:

            def matches(row: dict[str, Any]) -> bool:
                for name, value in selected.items():
                    if name == "document_id":
                        if row.get("document_id", row.get("id")) != value:
                            return False
                    elif name == "tag":
                        normalized = " ".join(
                            unicodedata.normalize("NFKC", value).casefold().split()
                        )
                        if not normalized or normalized not in row.get("tags", []):
                            return False
                    elif row.get(name, row.get("provenance", {}).get(name)) != value:
                        return False
                return True

            rows = [row for row in rows if matches(row)]
        if mode != "semantic":
            rows.sort(key=lambda row: str(row.get("id", "")))
        rows = [
            row
            for row in rows
            if corpus_revision is None or row.get("corpus_revision") == corpus_revision
        ]

        retrieved = self.now().isoformat()
        result = [
            row
            | {
                "match_mode": mode,
                "metadata_filtered": mode == "metadata",
                "retrieved_at": retrieved,
                "result_status": "complete",
            }
            for row in rows[:limit]
        ]
        self._response(result)
        await self._audit(
            "documentation-read",
            key or "multiple",
            "read",
            "allowed",
            len(result),
            corpus=corpus,
            match_mode=mode,
        )
        return result

    async def unsupported(self, operation: str) -> dict[str, str]:
        if operation not in {
            "vector",
            "ontology",
            "reindex",
            "document-delete",
            "corpus-delete",
        }:
            raise CapabilityError("Unknown operation")
        return {"status": "unsupported", "operation": operation}

    def _response(self, value: Any) -> None:
        if len(_canonical(value)) > MAX_RESPONSE_BYTES:
            raise CapabilityError("Response exceeds hard limit")

    def _audit_namespace(self) -> tuple[str, ...]:
        return (
            "app",
            "v1",
            "phase5-audit",
            f"tenant:{self.authority.tenant_id}",
            f"trust:{self.authority.trust_domain}",
            f"owner:person:{self.authority.owner_id}",
        )

    async def audit_event(
        self,
        *,
        operation: str,
        record_id: str,
        correlation: str,
        decision: str,
        count: int,
        corpus: str | None = None,
        match_mode: str | None = None,
        reason_class: str = "policy",
    ) -> None:
        """Write one content-free, schema-bounded Phase 5 audit event."""
        if (
            operation not in _PHASE5_AUDIT_OPERATIONS
            or decision not in _PHASE5_AUDIT_DECISIONS
            or reason_class not in _PHASE5_REASON_CLASSES
            or type(count) is not int
            or not 0 <= count <= MAX_CANDIDATES
        ):
            raise CapabilityError("Invalid audit event")
        _identifier(record_id, "audit record id")
        _identifier(correlation, "audit correlation")
        if corpus is not None:
            _identifier(corpus, "audit corpus")
        if match_mode is not None and match_mode not in {
            "exact",
            "metadata",
            "lexical",
            "semantic",
        }:
            raise CapabilityError("Invalid audit match mode")
        current = self.now()
        timestamp = current.isoformat()
        key = hashlib.sha256(
            f"{timestamp}:{correlation}:{operation}:{record_id}:{decision}".encode()
        ).hexdigest()
        event = {
            "record_id": record_id,
            "principal_id": self.authority.principal_id,
            "tenant_id": self.authority.tenant_id,
            "trust_domain": self.authority.trust_domain,
            "owner_id": self.authority.owner_id,
            "operation": operation,
            "decision": decision,
            "reason_class": reason_class,
            "correlation": correlation,
            "time": timestamp,
            "count": count,
            "expires_at": (current + AUDIT_RETENTION).isoformat(),
        }
        if corpus is not None:
            event["corpus"] = corpus
        if match_mode is not None:
            event["match_mode"] = match_mode
        await self.store.aput(
            self._audit_namespace(), key, event, index=False, ttl=AUDIT_TTL_MINUTES
        )

    async def _audit(
        self,
        action: str,
        record_id: str,
        correlation: str,
        decision: str,
        count: int,
        *,
        corpus: str | None = None,
        match_mode: str | None = None,
    ) -> None:
        await self.audit_event(
            operation=action,
            record_id=record_id,
            correlation=correlation,
            decision=decision,
            count=count,
            corpus=corpus,
            match_mode=match_mode,
        )

    async def read_audit(self, *, limit: int = MAX_RESULTS) -> list[dict[str, Any]]:
        self._permit("audit")
        if (
            self.authority.principal_id not in {"owner", self.authority.owner_id}
            or not 1 <= limit <= MAX_RESULTS
        ):
            raise CapabilityError("Owner-only audit access denied")
        namespace = self._audit_namespace()
        rows = await self._search(namespace)
        live = [
            {key: value for key, value in row.items() if key != "_key"}
            for row in rows
            if datetime.fromisoformat(str(row["expires_at"])) >= self.now()
        ]
        live.sort(
            key=lambda r: (str(r["time"]), str(r["correlation"]), str(r["record_id"]))
        )
        return live[:limit]
