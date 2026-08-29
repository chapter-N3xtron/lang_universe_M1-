"""Synthetic contract tests for one-person installation authentication."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langgraph_sdk import Auth

from src.installation_auth import (
    _authorized_namespace,
    authenticate,
    authorize_thread_create,
    authorize_threads,
    deny_unhandled,
    installation_identity,
)

_ENV = {
    "INSTALLATION_OWNER_API_KEY": "synthetic-secret-value",
    "INSTALLATION_TENANT_ID": "tenant_opaque_01",
    "INSTALLATION_OWNER_ID": "owner_opaque_01",
}


def test_auth_returns_only_server_derived_scope_and_no_key():
    with patch.dict(os.environ, _ENV, clear=False):
        result = asyncio.run(
            authenticate({b"x-api-key": b"synthetic-secret-value", b"owner": b"attacker"})
        )
    assert result["identity"] == "owner_opaque_01"
    assert result["tenant_id"] == "tenant_opaque_01"
    assert result["trust_domain"] == "local-installation-v1"
    assert "synthetic-secret-value" not in repr(result)
    assert "attacker" not in repr(result)


@pytest.mark.parametrize("headers", [{}, {b"x-api-key": b"wrong"}])
def test_auth_fails_closed_without_matching_key(headers):
    with patch.dict(os.environ, _ENV, clear=False), pytest.raises(
        Auth.exceptions.HTTPException
    ) as raised:
        asyncio.run(authenticate(headers))
    assert raised.value.status_code == 401
    assert "synthetic-secret-value" not in str(raised.value)


def test_auth_fails_closed_without_server_identity():
    env = {"INSTALLATION_OWNER_API_KEY": "synthetic-secret-value"}
    with patch.dict(os.environ, env, clear=True), pytest.raises(
        Auth.exceptions.HTTPException
    ) as raised:
        asyncio.run(authenticate({b"x-api-key": b"synthetic-secret-value"}))
    assert raised.value.status_code == 503


def test_installation_identity_never_accepts_caller_scope():
    with patch.dict(os.environ, _ENV, clear=False):
        first = installation_identity()
        second = installation_identity()
    assert first == second
    assert first["owner_type"] == "person"


def _ctx(owner="owner_opaque_01", tenant="tenant_opaque_01"):
    return SimpleNamespace(user=SimpleNamespace(identity=owner, tenant_id=tenant))


def test_authorization_denies_unhandled_and_filters_threads_at_server():
    assert asyncio.run(deny_unhandled(_ctx(), {})) is False
    assert asyncio.run(authorize_threads(_ctx(), {"owner_id": "attacker"})) == {
        "owner_id": "owner_opaque_01"
    }


def test_thread_create_overwrites_each_caller_scope_dimension():
    value = {"graph_id": "chat_ui", "metadata": {"owner_id": "other", "tenant_id": "other"}}
    assert asyncio.run(authorize_thread_create(_ctx(), value)) is True
    assert value["metadata"]["owner_id"] == "owner_opaque_01"
    assert value["metadata"]["tenant_id"] == "tenant_opaque_01"
    value["graph_id"] = "unknown"
    assert asyncio.run(authorize_thread_create(_ctx(), value)) is False


@pytest.mark.parametrize(
    "namespace,allowed",
    [
        (("app", "v1", "cross-session-memory", "tenant:tenant_opaque_01", "trust:local-installation-v1", "owner:person:owner_opaque_01", "kind:task-outcomes"), True),
        (("app", "v1", "documentation-retrieval", "tenant:tenant_opaque_01", "trust:local-installation-v1", "owner:person:owner_opaque_01", "corpus:installation-docs", "record:fragment"), True),
        (("app", "v1", "cross-session-memory", "tenant:other", "trust:local-installation-v1", "owner:person:owner_opaque_01", "kind:task-outcomes"), False),
        (("app", "v1", "cross-session-memory", "tenant:tenant_opaque_01", "trust:other", "owner:person:owner_opaque_01", "kind:task-outcomes"), False),
        (("app", "v1", "cross-session-memory", "tenant:tenant_opaque_01", "trust:local-installation-v1", "owner:person:other", "kind:task-outcomes"), False),
        (("app", "v1", "arbitrary", "tenant:tenant_opaque_01", "owner:person:owner_opaque_01"), False),
        ((), False),
    ],
)
def test_store_namespace_authorization_varies_one_dimension(namespace, allowed):
    assert _authorized_namespace(_ctx(), {"namespace": namespace}) is allowed
