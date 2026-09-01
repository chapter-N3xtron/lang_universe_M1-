"""Fail-closed custom authentication for a one-person Agent Server installation."""

from __future__ import annotations

import hmac
import os
from typing import Any

from langgraph_sdk import Auth

LEGACY_OWNER_ID = "local-owner-v1"
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
) -> dict[str, str]:
    """Stamp the documented thread-create payload with installation scope."""
    owner_filter = _owner_filter(ctx)
    metadata = value.setdefault("metadata", {})
    metadata.update(
        owner_filter
        | {
            "tenant_id": str(ctx.user.tenant_id),
            "trust_domain": TRUST_DOMAIN,
        }
    )
    return owner_filter


@auth.on(resources=["threads"], actions=["read", "search", "update", "delete"])
async def authorize_threads(ctx: Auth.types.AuthContext, value: Any) -> bool:
    """Allow the authenticated sole owner to access this installation's threads."""
    return True


@auth.on.threads.create_run
async def authorize_runs(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """Allow the authenticated sole owner to run configured assistants."""
    return bool(value.get("assistant_id"))


@auth.on.assistants.read
async def authorize_assistant_read(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Allow exact reads of server-configured assistants in this one-owner install."""
    return bool(value.get("assistant_id"))


@auth.on.assistants.search
async def authorize_assistant_search(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Permit listing in this one-owner installation; exact reads stay allowlisted."""
    return True


def _authorized_legacy_namespace(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Preserve only the pre-Phase-5 raw Store namespace contract."""
    namespace = tuple(str(part) for part in value.get("namespace") or ())
    return (
        len(namespace) >= 2
        and namespace[0] in {str(ctx.user.identity), LEGACY_OWNER_ID}
        and namespace[1] in ALLOWED_LEGACY_STORE_FAMILIES
    )


async def authorize_store(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> bool:
    """Preserve only legacy browser Store access; Phase 5 uses graph operations."""
    return _authorized_legacy_namespace(ctx, value)


@auth.on.store.get
async def authorize_store_get(
    ctx: Auth.types.AuthContext, value: Auth.types.StoreGet
) -> bool:
    """Deny Phase 5 direct reads while preserving the legacy Store contract."""
    return _authorized_legacy_namespace(ctx, value)


@auth.on.store.search
async def authorize_store_search(
    ctx: Auth.types.AuthContext, value: Auth.types.StoreSearch
) -> bool:
    """Deny Phase 5 direct search while preserving the legacy Store contract."""
    return _authorized_legacy_namespace(ctx, value)


# Compatibility alias for imports which predate the action-specific read split.
authorize_store_read = authorize_store_get


@auth.on.store.put
@auth.on.store.delete
async def authorize_store_mutation(
    ctx: Auth.types.AuthContext, value: dict[str, Any]
) -> bool:
    """Deny Phase 5 writes; preserve the exact legacy mutation policy."""
    return _authorized_legacy_namespace(ctx, value)


@auth.on.store.list_namespaces
async def deny_store_namespace_listing(ctx: Auth.types.AuthContext, value: Any) -> bool:
    return False
