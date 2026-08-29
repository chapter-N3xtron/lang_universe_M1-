"""Fail-closed custom authentication for a one-person Agent Server installation."""

from __future__ import annotations

import hmac
import os
from typing import Any

from langgraph_sdk import Auth

ALLOWED_GRAPHS = frozenset({"chat_ui", "coder"})
ALLOWED_STORE_FAMILIES = frozenset(
    {
        "cross-session-memory",
        "documentation-retrieval",
        "phase5-audit",
    }
)
ALLOWED_LEGACY_STORE_FAMILIES = frozenset(
    {
        "preferences",
        "sessions",
        "session-artifacts",
        "session-library-views",
        "reports",
        "research-evidence",
    }
)

TRUST_DOMAIN = "local-installation-v1"
OWNER_PERMISSIONS = (
    "cross-session-memory:read",
    "cross-session-memory:write",
    "cross-session-memory:delete",
    "cross-session-memory:restore",
    "cross-session-memory:permanent-delete",
    "cross-session-memory:audit",
    "documentation-retrieval:read",
)

auth = Auth()


def installation_identity() -> dict[str, object]:
    """Load only server-controlled identity; absence is a deployment error."""
    tenant = os.getenv("INSTALLATION_TENANT_ID", "")
    owner = os.getenv("INSTALLATION_OWNER_ID", "")
    if not tenant or not owner or len(tenant) > 128 or len(owner) > 128:
        raise RuntimeError("Installation identity is not configured.")
    return {
        "identity": owner,
        "tenant_id": tenant,
        "trust_domain": TRUST_DOMAIN,
        "owner_type": "person",
        "owner_id": owner,
        "permissions": list(OWNER_PERMISSIONS),
        "corpus_grants": ["installation-docs"],
    }


@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    """Authenticate X-Api-Key without returning or logging credential material."""
    expected = os.getenv("INSTALLATION_OWNER_API_KEY", "")
    supplied = headers.get(b"x-api-key") or headers.get("x-api-key")
    if isinstance(supplied, bytes):
        supplied = supplied.decode("utf-8", errors="replace")
    if not expected or not supplied or not hmac.compare_digest(str(supplied), expected):
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Authentication failed."
        )
    try:
        return installation_identity()  # type: ignore[return-value]
    except RuntimeError as exc:
        raise Auth.exceptions.HTTPException(
            status_code=503, detail="Installation identity is unavailable."
        ) from exc


@auth.on
async def deny_unhandled(ctx: Auth.types.AuthContext, value: Any) -> bool:
    """Default deny is essential: authentication is not authorization."""
    return False


def _owner_filter(ctx: Auth.types.AuthContext) -> dict[str, str]:
    return {"owner_id": str(ctx.user.identity)}


@auth.on.threads.create
async def authorize_thread_create(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    metadata = value.setdefault("metadata", {})
    graph_id = str(value.get("graph_id") or metadata.get("graph_id") or "")
    if graph_id not in ALLOWED_GRAPHS:
        return False
    metadata["owner_id"] = str(ctx.user.identity)
    metadata["tenant_id"] = str(ctx.user.tenant_id)
    metadata["trust_domain"] = TRUST_DOMAIN
    return True


@auth.on(resources=["threads"], actions=["read", "search", "update", "delete"])
async def authorize_threads(ctx: Auth.types.AuthContext, value: Any) -> dict[str, str]:
    return _owner_filter(ctx)


@auth.on.threads.create_run
async def authorize_runs(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """langgraph-api 0.11.2 authorizes run creation as threads:create_run."""
    graph_id = str(value.get("assistant_id") or value.get("graph_id") or "")
    return graph_id in ALLOWED_GRAPHS


@auth.on.assistants.read
async def authorize_assistant_read(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    assistant_id = str(value.get("assistant_id") or value.get("graph_id") or "")
    return assistant_id in ALLOWED_GRAPHS


@auth.on.assistants.search
async def authorize_assistant_search(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> dict[str, Any]:
    return {"graph_id": {"$in": sorted(ALLOWED_GRAPHS)}}


def _authorized_namespace(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    namespace = tuple(str(part) for part in value.get("namespace") or ())
    owner, tenant = str(ctx.user.identity), str(ctx.user.tenant_id)
    if len(namespace) >= 3 and namespace[:2] == ("app", "v1"):
        family = namespace[2]
        if family not in ALLOWED_STORE_FAMILIES:
            return False
        required = {f"tenant:{tenant}", f"owner:person:{owner}"}
        if not required.issubset(namespace):
            return False
        if family == "cross-session-memory":
            return (
                len(namespace) == 7
                and f"trust:{TRUST_DOMAIN}" in namespace
                and namespace[6].startswith("kind:")
            )
        if family == "documentation-retrieval":
            return (
                len(namespace) == 8
                and f"trust:{TRUST_DOMAIN}" in namespace
                and namespace[6].startswith("corpus:")
                and namespace[7]
                in {"record:fragment", "record:document", "record:operation"}
            )
        return len(namespace) == 5
    return (
        len(namespace) >= 2
        and namespace[0] == owner
        and namespace[1] in ALLOWED_LEGACY_STORE_FAMILIES
    )


async def authorize_store(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """Compatibility helper: raw Phase 5 access is always denied."""
    namespace = tuple(str(part) for part in value.get("namespace") or ())
    return _authorized_namespace(ctx, value) and namespace[:2] != ("app", "v1")


@auth.on.store.get
@auth.on.store.search
async def authorize_store_read(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Deny every raw Phase 5 read/search; capabilities use Runtime.store."""
    namespace = tuple(str(part) for part in value.get("namespace") or ())
    return _authorized_namespace(ctx, value) and namespace[:2] != ("app", "v1")


@auth.on.store.put
@auth.on.store.delete
async def authorize_store_mutation(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Raw Phase 5 writes are denied; trusted graph adapters use injected Store."""
    namespace = tuple(str(part) for part in value.get("namespace") or ())
    return _authorized_namespace(ctx, value) and namespace[:2] != ("app", "v1")


@auth.on.store.list_namespaces
async def deny_store_namespace_listing(ctx: Auth.types.AuthContext, value: Any) -> bool:
    return False
