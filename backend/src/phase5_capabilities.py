r"""Phase 5 trusted capabilities over the public Agent Server Store API.

Lexical matching is deliberately non-semantic: Unicode text is NFKC/casefolded,
words are ``\w+`` tokens, score is the number of distinct query tokens present,
and ties are ordered by record id. Store values are immutable revisions; a head
is resolved deterministically from revision records, so no Store CAS is assumed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
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
        "user-preferences",
        "user-provided-facts",
        "project-decisions",
        "task-outcomes",
        "reusable-instructions",
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
MAX_RESULTS = 20
MAINTENANCE_HARD_CAP = 1000
MAX_FILTERS = 8
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
    operation_id: str
    operation_key: str
    request_digest: str
    memory_id: str
    envelope: dict[str, Any]
    write_revision: bool
    write_head: bool
    write_operation: bool


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
            corpora = delegated_corpora or frozenset({"installation-docs"})
            principal_id = "owner"
        elif principal in {"jasper", "coder", "librarian"}:
            allowed = frozenset({"read", "write", "delete"})
            if not delegated_memory <= allowed:
                raise CapabilityError("Unsupported specialist delegation")
            memory, corpora = delegated_memory, delegated_corpora
        elif principal == "ocr":
            if delegated_memory:
                raise CapabilityError("OCR cannot receive memory grants")
            memory, corpora = frozenset(), frozenset()
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


def _identifier(value: Any, label: str = "identifier") -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise CapabilityError(f"Invalid {label}")
    return value


def memory_namespace(
    auth: Authority, kind: str, record: str = "head", record_id: str | None = None
) -> tuple[str, ...]:
    if type(kind) is not str or kind not in MEMORY_KINDS:
        raise CapabilityError("Unsupported memory kind")
    if record not in {"head", "revision", "operation"}:
        raise CapabilityError("Invalid memory scope")
    namespace = (
        "app",
        "v1",
        "cross-session-memory",
        f"tenant:{auth.tenant_id}",
        f"trust:{auth.trust_domain}",
        f"owner:person:{auth.owner_id}",
        f"kind:{kind}",
        f"record:{record}",
    )
    if record == "revision":
        return namespace + (f"id:{_identifier(record_id, 'memory id')}",)
    if record_id is not None:
        raise CapabilityError("Record id is only valid for revisions")
    return namespace


def documentation_namespace(
    auth: Authority, corpus: str, record: str = "fragment"
) -> tuple[str, ...]:
    _identifier(corpus, "corpus")
    if record not in {"fragment", "document", "operation"}:
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


def issue_token(
    payload: dict[str, Any], secret: bytes, *, now: datetime, ttl_seconds: int = 300
) -> str:
    if (
        type(payload) is not dict
        or type(secret) is not bytes
        or not secret
        or type(ttl_seconds) is not int
        or not 1 <= ttl_seconds <= 900
    ):
        raise CapabilityError("Invalid token policy")
    body = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + ttl_seconds,
    }
    encoded = base64.urlsafe_b64encode(_canonical(body)).rstrip(b"=")
    return (
        encoded
        + b"."
        + base64.urlsafe_b64encode(
            hmac.new(secret, encoded, hashlib.sha256).digest()
        ).rstrip(b"=")
    ).decode("ascii")


def verify_token(
    token: str, secret: bytes, expected: dict[str, Any], *, now: datetime
) -> dict[str, Any]:
    try:
        encoded, supplied = token.encode("ascii").split(b".", 1)
        signature = base64.urlsafe_b64decode(supplied + b"=" * (-len(supplied) % 4))
        body = json.loads(
            base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
        )
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise CapabilityError("Invalid capability token") from exc
    if type(body) is not dict or not hmac.compare_digest(
        signature, hmac.new(secret, encoded, hashlib.sha256).digest()
    ):
        raise CapabilityError("Invalid capability token")
    if (
        type(body.get("exp")) is not int
        or body["exp"] < int(now.timestamp())
        or any(body.get(k) != v for k, v in expected.items())
    ):
        raise CapabilityError("Expired or out-of-scope capability token")
    return body


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
        raise CapabilityError("Memory metadata exceeds bounds")
    return value


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
        self, namespace: tuple[str, ...], *, limit: int = MAX_CANDIDATES
    ) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
            raise CapabilityError("Candidate bound exceeded")
        result = await self.store.asearch(namespace, limit=limit, offset=0)
        if len(result) > limit:
            raise CapabilityError("Store exceeded candidate bound")
        return [
            {
                "_key": str(
                    item.get("key", item.get("id", ""))
                    if isinstance(item, dict)
                    else item.key
                ),
                **_value(item),
            }
            for item in result
        ]

    async def _head(
        self, namespace: tuple[str, ...], memory_id: str
    ) -> dict[str, Any] | None:
        """Resolve an exact head without ever scanning revision history."""
        item = await self.store.aget(namespace, memory_id)
        if item is None:
            return None
        return {"_key": memory_id, **_value(item)}

    async def _heads(self, namespace: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        """Scan only the bounded materialized-head namespace."""
        rows = await self._search(namespace)
        return {
            str(row["id"]): row
            for row in rows
            if row.get("record_type") in {"memory-revision", "memory"}
            and row.get("id")
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
        """Validate and inspect one write without mutating the Store."""
        self._permit("write")
        namespace = memory_namespace(self.authority, kind)
        _validate_content(content, content_class)
        _validate_string_map(metadata, metadata=True)
        _validate_string_map(provenance)
        required = {"source_type", "source_id", "actor"}
        if not required <= set(provenance):
            raise CapabilityError("Incomplete memory provenance")
        # Creation method is a server fact, not a caller-selectable authority. Source time
        # remains explicitly unknown when the creating caller has no verified value.
        provenance = {
            "source_time": "unknown",
            **provenance,
            "creation_method": "explicit-authorized-write",
        }
        _validate_string_map(provenance)
        # Preserve bounded, non-secret source attributes rather than silently dropping
        # provenance that a future schema can understand. Required authority still comes
        # exclusively from Authority, never from this untrusted map.
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
        operation_key = f"operation:{operation_id}"
        operation_namespace = memory_namespace(self.authority, kind, "operation")
        revision_namespace = memory_namespace(
            self.authority, kind, "revision", memory_id
        )
        manifest = _value(await self.store.aget(operation_namespace, operation_key))
        if manifest and (
            manifest.get("request_digest") != request_digest
            or manifest.get("memory_id") != memory_id
        ):
            raise CapabilityError("Idempotency key conflict")
        head = await self._head(namespace, memory_id)
        revision = _value(await self.store.aget(revision_namespace, "revision:00000001"))
        stored = ({k: v for k, v in head.items() if k != "_key"} if head else revision)
        if stored:
            stored_request = {key: stored.get(key) for key in request}
            if _digest(stored_request) != request_digest:
                raise CapabilityError("Idempotency key conflict")
            envelope = stored
        else:
            envelope = {
                "schema_version": 1,
                "record_type": "memory-revision",
                "id": memory_id,
                **request,
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
                "purged_at": None,
            }
        return _MemoryWritePlan(
            kind, operation_id, operation_key, request_digest, memory_id, envelope,
            not bool(revision), not bool(head), not bool(manifest),
        )

    async def _check_write_capacity(self, plans: list[_MemoryWritePlan]) -> None:
        additions: dict[str, int] = {}
        for plan in plans:
            if plan.write_head:
                additions[plan.kind] = additions.get(plan.kind, 0) + len(
                    _canonical(plan.envelope)
                )
        for kind, addition in additions.items():
            heads = await self._heads(memory_namespace(self.authority, kind))
            used = sum(
                len(_canonical({k: v for k, v in row.items() if k != "_key"}))
                for row in heads.values()
                if not row.get("purged_at")
            )
            if used + addition > MAX_KIND_BYTES:
                raise CapabilityError("Memory kind capacity exceeded; no eviction performed")

    async def _execute_write_plan(self, plan: _MemoryWritePlan) -> dict[str, Any]:
        # These deterministic writes reconcile a prior backend partial failure. They do
        # not claim transaction atomicity from the Store backend.
        if plan.write_revision:
            await self.store.aput(
                memory_namespace(self.authority, plan.kind, "revision", plan.memory_id),
                "revision:00000001", plan.envelope, index=False,
            )
        if plan.write_head:
            await self.store.aput(
                memory_namespace(self.authority, plan.kind),
                plan.memory_id, plan.envelope, index=False,
            )
        if plan.write_operation:
            await self.store.aput(
                memory_namespace(self.authority, plan.kind, "operation"),
                plan.operation_key,
                {"record_type": "operation", "memory_id": plan.memory_id,
                 "request_digest": plan.request_digest},
                index=False,
            )
        if plan.write_revision or plan.write_head or plan.write_operation:
            await self._audit("write", plan.memory_id, plan.operation_id, "allowed", 1)
        return plan.envelope

    async def write_memory(
        self, *, kind: str, content: str, metadata: dict[str, str],
        provenance: dict[str, str], operation_id: str,
        content_class: str = "ordinary",
    ) -> dict[str, Any]:
        plan = await self._validated_write_plan(
            kind=kind, content=content, metadata=metadata, provenance=provenance,
            operation_id=operation_id, content_class=content_class,
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
        allowed = {"kind", "content", "metadata", "provenance", "operation_id", "content_class"}
        required = {"kind", "content", "metadata", "provenance", "operation_id"}
        seen: set[str] = set()
        timestamp = self.now().isoformat()
        plans: list[_MemoryWritePlan] = []
        for item in writes:
            if type(item) is not dict or set(item) - allowed or not required <= set(item):
                raise CapabilityError("Invalid write batch item")
            operation = str(item["operation_id"])
            if operation in seen:
                raise CapabilityError("Duplicate operation id")
            seen.add(operation)
            plans.append(await self._validated_write_plan(
                kind=item["kind"], content=item["content"], metadata=item["metadata"],
                provenance=item["provenance"], operation_id=item["operation_id"],
                content_class=item.get("content_class", "ordinary"), timestamp=timestamp,
            ))
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
        if mode == "exact":
            _identifier(key, "memory id")
            head = await self._head(namespace, key)
            rows = [head] if head is not None else []
        elif mode in {"metadata", "lexical"}:
            rows = list((await self._heads(namespace)).values())
        else:
            raise CapabilityError("Unsupported match mode")
        rows = [
            r
            for r in rows
            if not r.get("deleted_at")
            and not r.get("purged_at")
            and r.get("lifecycle_state", "active") == "active"
        ]
        if mode == "metadata":
            selected = self._filters(filters, {"source_type", "source_id"})
            rows = [
                r
                for r in rows
                if all(r.get("provenance", {}).get(k) == v for k, v in selected.items())
            ]
            rows.sort(key=lambda row: str(row["id"]))
        elif mode == "lexical":
            rows = lexical_rank(_query(query), rows)
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
        if action in {"restore", "permanent-delete"} and self.authority.principal_id not in {
            "owner",
            self.authority.owner_id,
        }:
            raise CapabilityError("Owner-only lifecycle access denied")
        _identifier(memory_id, "memory id")
        _identifier(operation_id, "operation id")
        namespace = memory_namespace(self.authority, kind)
        operation_namespace = memory_namespace(self.authority, kind, "operation")
        request_digest = _digest(
            {"action": action, "id": memory_id, "expected_revision": expected_revision}
        )
        op_key = f"operation:{operation_id}"
        previous = _value(await self.store.aget(operation_namespace, op_key))
        row = await self._head(namespace, memory_id)
        if previous:
            if previous.get("request_digest") != request_digest:
                raise CapabilityError("Idempotency key conflict")
            return row or {"id": memory_id, "purged": True}
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
        if action == "delete":
            changes = {
                "deleted_at": row.get("deleted_at") or now.isoformat(),
                "lifecycle_state": "deleted",
            }
        elif action == "restore":
            if not deleted or now > deleted + RESTORE_WINDOW or row.get("purged_at"):
                raise CapabilityError("Memory is not restorable")
            changes = {"deleted_at": None, "lifecycle_state": "active"}
        else:
            if not deleted:
                raise CapabilityError(
                    "Permanent delete requires an exact deleted memory"
                )
            changes = {
                "purged_at": now.isoformat(),
                "content": "",
                "metadata": {},
                "lifecycle_state": "purged",
            }
        revision = int(row["revision"]) + 1
        updated = (
            {k: v for k, v in row.items() if k != "_key"}
            | changes
            | {
                "revision": revision,
                "updated_at": now.isoformat(),
                "operation_id": operation_id,
                "record_type": "memory-revision",
            }
        )
        if action == "permanent-delete":
            # Immutable revisions are never overwritten, but purge must physically
            # remove every content-bearing revision before writing its tombstone.
            revision_namespace = memory_namespace(
                self.authority, kind, "revision", memory_id
            )
            for stored in await self._search(revision_namespace):
                await self.store.adelete(revision_namespace, stored["_key"])
            await self.store.adelete(namespace, memory_id)
        else:
            await self.store.aput(
                memory_namespace(self.authority, kind, "revision", memory_id),
                f"revision:{revision:08d}",
                updated,
                index=False,
            )
            await self.store.aput(namespace, memory_id, updated, index=False)
        await self.store.aput(
            operation_namespace,
            op_key,
            {
                "record_type": "operation",
                "memory_id": memory_id,
                "request_digest": request_digest,
            },
            index=False,
        )
        await self._audit(action, memory_id, operation_id, "allowed", 1)
        return (
            {"id": memory_id, "purged": True}
            if action == "permanent-delete"
            else updated
        )

    async def purge_eligible(self, kind: str, *, limit: int = MAX_RESULTS) -> int:
        self._permit("permanent-delete")
        if not 1 <= limit <= MAX_RESULTS:
            raise CapabilityError("Invalid result bound")
        heads = await self._heads(memory_namespace(self.authority, kind))
        count = 0
        for row in sorted(heads.values(), key=lambda r: str(r["id"])):
            if count >= limit:
                break
            if (
                row.get("deleted_at")
                and self.now()
                > datetime.fromisoformat(row["deleted_at"]) + RESTORE_WINDOW
                and not row.get("purged_at")
            ):
                await self._lifecycle(
                    kind,
                    row["id"],
                    f"scheduled-{row['id']}-{row['revision']}",
                    "permanent-delete",
                    row["revision"],
                )
                count += 1
        return count

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
    ) -> dict[str, Any]:
        self._permit("documentation-retrieval:write", corpus)
        if not supervisor_approved or not ocr_succeeded:
            raise CapabilityError("Documentation write denied")
        _identifier(fragment_id, "fragment id")
        _identifier(operation_id, "operation id")
        _identifier(corpus_revision, "corpus revision")
        _validate_content(content, content_class)
        _validate_string_map(provenance)
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
        _identifier(provenance["document_id"], "document id")
        namespace = documentation_namespace(self.authority, corpus)
        request_digest = _digest(
            {
                "corpus": corpus,
                "fragment_id": fragment_id,
                "content": content,
                "provenance": provenance,
                "corpus_revision": corpus_revision,
            }
        )
        op_ns = documentation_namespace(self.authority, corpus, "operation")
        op_key = f"operation:{operation_id}"
        prior = _value(await self.store.aget(op_ns, op_key))
        if prior:
            if prior.get("request_digest") != request_digest:
                raise CapabilityError("Idempotency key conflict")
            return _value(
                await self.store.aget(namespace, str(prior["record_key"]))
            )
        key = f"fragment:{fragment_id}:corpus-revision:{corpus_revision}"
        if await self.store.aget(namespace, key):
            raise CapabilityError("Immutable documentation record already exists")
        now = self.now().isoformat()
        record = {
            "schema_version": 1,
            "record_type": "fragment",
            "id": fragment_id,
            "content": content,
            "corpus": corpus,
            "corpus_revision": corpus_revision,
            "document_id": provenance["document_id"],
            "fragment_id": fragment_id,
            "locator": provenance["locator"],
            "title": provenance["title"],
            "source_uri": provenance.get("source_uri", "unknown"),
            "source_revision": provenance["source_revision"],
            "digest": provenance["digest"],
            "source_time": provenance.get("source_time", "unknown"),
            "source_status": provenance["source_status"],
            "source_type": provenance["source_type"],
            "provenance": provenance,
            "operation_id": operation_id,
            "created_at": now,
            "untrusted_data": True,
        }
        try:
            await self.store.aput(namespace, key, record, index=False)
            await self.store.aput(
                op_ns,
                op_key,
                {
                    "record_type": "operation",
                    "record_key": key,
                    "request_digest": request_digest,
                },
                index=False,
            )
        except Exception:
            # A fragment without its idempotency manifest is not a committed corpus
            # write. Best-effort rollback keeps ordinary backend failures fail-closed.
            try:
                await self.store.adelete(namespace, key)
                await self.store.adelete(op_ns, op_key)
            except Exception:
                pass
            raise
        await self._audit(
            "documentation-write",
            fragment_id,
            operation_id,
            "allowed",
            1,
            corpus=corpus,
        )
        return record

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
    ) -> list[dict[str, Any]]:
        self._permit("documentation-retrieval:read", corpus)
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise CapabilityError("Invalid result bound")
        namespace = documentation_namespace(self.authority, corpus)
        rows = await self._search(namespace)
        unknown_lifecycle = any(
            row.get("record_type") == "fragment"
            and row.get(
                "source_status", row.get("provenance", {}).get("source_status")
            )
            not in DOC_ACTIVE | DOC_INACTIVE
            for row in rows
        )
        if mode == "exact":
            _identifier(key, "document or fragment id")
            rows = [
                r
                for r in rows
                if r.get("id") == key or r.get("document_id") == key
            ]
        elif mode in {"metadata", "metadata+lexical"}:
            selected = self._filters(
                filters,
                {"document_id", "source_type", "source_revision", "source_status"},
            )
            rows = [
                r
                for r in rows
                if all(
                    r.get(k, r.get("provenance", {}).get(k)) == v
                    for k, v in selected.items()
                )
            ]
            if mode == "metadata+lexical":
                rows = lexical_rank(_query(query), rows)
        elif mode == "lexical":
            rows = lexical_rank(_query(query), rows)
        else:
            raise CapabilityError("Unsupported match mode")
        rows = [
            r
            for r in rows
            if r.get("record_type") == "fragment"
            and r.get("source_status", r.get("provenance", {}).get("source_status"))
            in DOC_ACTIVE
            and (corpus_revision is None or r.get("corpus_revision") == corpus_revision)
        ]
        if mode != "lexical":
            rows.sort(
                key=lambda r: (str(r.get("id", "")), str(r.get("corpus_revision", "")))
            )
        if unknown_lifecycle:
            raise CapabilityError("Documentation lifecycle verification failed")
        retrieved = self.now().isoformat()
        result = []
        for row in rows[:limit]:
            clean = {k: v for k, v in row.items() if k != "_key"}
            result.append(
                clean
                | {
                    # Combined filtering remains lexical matching, not a fourth
                    # retrieval technology. Report filtering independently.
                    "match_mode": "lexical" if mode == "metadata+lexical" else mode,
                    "metadata_filtered": mode in {"metadata", "metadata+lexical"},
                    "retrieved_at": retrieved,
                    "result_status": "complete",
                }
            )
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

    async def maintain(
        self,
        *,
        per_kind_limit: int = MAX_RESULTS,
        audit_hard_cap: int = MAINTENANCE_HARD_CAP,
    ) -> dict[str, int]:
        """Bounded lazy maintenance; deployment scheduling is configured separately."""
        self._permit("permanent-delete")
        if type(audit_hard_cap) is not int or not 1 <= audit_hard_cap <= MAINTENANCE_HARD_CAP:
            raise CapabilityError("Invalid maintenance bound")
        purged = 0
        for kind in sorted(MEMORY_KINDS):
            purged += await self.purge_eligible(kind, limit=per_kind_limit)
        namespace = self._audit_namespace()
        inspected = 0
        expired_keys: list[str] = []
        while inspected < audit_hard_cap:
            page_limit = min(MAX_RESULTS, audit_hard_cap - inspected)
            rows = await self.store.asearch(
                namespace, limit=page_limit, offset=inspected
            )
            if not rows:
                break
            for item in rows:
                value = _value(item)
                if datetime.fromisoformat(str(value["expires_at"])) < self.now():
                    key = (
                        str(item.get("key", item.get("id", "")))
                        if isinstance(item, dict)
                        else item.key
                    )
                    expired_keys.append(key)
            inspected += len(rows)
            if len(rows) < page_limit:
                break
        for key in expired_keys:
            await self.store.adelete(namespace, key)
        return {"purged": purged, "expired_audits": len(expired_keys)}

    async def unsupported(self, operation: str) -> dict[str, str]:
        if operation not in {
            "semantic",
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
        if match_mode is not None and match_mode not in {"exact", "metadata", "lexical", "metadata+lexical"}:
            raise CapabilityError("Invalid audit match mode")
        timestamp = self.now().isoformat()
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
            "expires_at": (self.now() + AUDIT_RETENTION).isoformat(),
        }
        if corpus is not None:
            event["corpus"] = corpus
        if match_mode is not None:
            event["match_mode"] = match_mode
        await self.store.aput(self._audit_namespace(), key, event, index=False)

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

    async def read_audit(
        self, *, limit: int = MAX_RESULTS, prune: bool = False
    ) -> list[dict[str, Any]]:
        self._permit("audit")
        if (
            self.authority.principal_id not in {"owner", self.authority.owner_id}
            or not 1 <= limit <= MAX_RESULTS
        ):
            raise CapabilityError("Owner-only audit access denied")
        namespace = (
            "app",
            "v1",
            "phase5-audit",
            f"tenant:{self.authority.tenant_id}",
            f"owner:person:{self.authority.owner_id}",
        )
        rows = await self._search(namespace)
        live = []
        for row in rows:
            if datetime.fromisoformat(str(row["expires_at"])) < self.now():
                if prune:
                    await self.store.adelete(namespace, row["_key"])
            else:
                live.append({k: v for k, v in row.items() if k != "_key"})
        live.sort(
            key=lambda r: (str(r["time"]), str(r["correlation"]), str(r["record_id"]))
        )
        return live[:limit]
