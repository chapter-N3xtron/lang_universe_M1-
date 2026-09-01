"""Synthetic contract tests for one-person installation authentication."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langgraph_sdk import Auth

from src.installation_auth import (
    _authorized_legacy_namespace,
    authenticate,
    authorize_assistant_read,
    authorize_assistant_search,
    authorize_runs,
    authorize_store_get,
    authorize_store_mutation,
    authorize_store_search,
    authorize_thread_create,
    authorize_threads,
    deny_store_namespace_listing,
    deny_unhandled,
    installation_identity,
)

DOCUMENTATION_DOCUMENTS_NAMESPACE = ("installation-docs", "documents")
DOCUMENTATION_FRAGMENTS_NAMESPACE = ("installation-docs", "fragments")

_ENV = {
    "INSTALLATION_OWNER_API_KEY": "synthetic-secret-value",
    "INSTALLATION_TENANT_ID": "tenant_opaque_01",
    "INSTALLATION_OWNER_ID": "owner_opaque_01",
}


def test_auth_returns_only_server_derived_scope_and_no_key():
    with patch.dict(os.environ, _ENV, clear=False):
        result = asyncio.run(
            authenticate(
                {b"x-api-key": b"synthetic-secret-value", b"owner": b"attacker"}
            )
        )
    assert result["identity"] == "owner_opaque_01"
    assert result["tenant_id"] == "tenant_opaque_01"
    assert result["trust_domain"] == "local-installation-v1"
    assert "synthetic-secret-value" not in repr(result)
    assert "attacker" not in repr(result)


@pytest.mark.parametrize("headers", [{}, {b"x-api-key": b"wrong"}])
def test_auth_fails_closed_without_matching_key(headers):
    with (
        patch.dict(os.environ, _ENV, clear=False),
        pytest.raises(Auth.exceptions.HTTPException) as raised,
    ):
        asyncio.run(authenticate(headers))
    assert raised.value.status_code == 401
    assert "synthetic-secret-value" not in str(raised.value)


def test_auth_fails_closed_without_server_identity():
    env = {"INSTALLATION_OWNER_API_KEY": "synthetic-secret-value"}
    with (
        patch.dict(os.environ, env, clear=True),
        pytest.raises(Auth.exceptions.HTTPException) as raised,
    ):
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


def test_authorization_denies_unhandled_and_allows_one_installation_threads():
    assert asyncio.run(deny_unhandled(_ctx(), {})) is False
    assert asyncio.run(authorize_threads(_ctx(), {"owner_id": "attacker"})) is True


def test_thread_create_accepts_documented_shape_and_stamps_server_scope():
    value = {
        "thread_id": "thread-1",
        "metadata": {
            "owner_id": "other",
            "tenant_id": "other",
            "trust_domain": "other",
        },
        "if_exists": "raise",
    }
    assert asyncio.run(authorize_thread_create(_ctx(), value)) == {
        "owner_id": "owner_opaque_01"
    }
    assert value["metadata"] == {
        "owner_id": "owner_opaque_01",
        "tenant_id": "tenant_opaque_01",
        "trust_domain": "local-installation-v1",
    }
    assert "graph_id" not in value


def test_run_creation_requires_a_server_configured_assistant_id():
    run = {"assistant_id": "fde89690-32c3-5cb8-92a9-66ce73d9514a"}
    assert asyncio.run(authorize_runs(_ctx(), run)) is True
    assert asyncio.run(authorize_runs(_ctx(), {})) is False


def test_assistant_search_and_exact_reads_allow_server_configured_assistants():
    assert (
        asyncio.run(authorize_assistant_search(_ctx(), {"limit": 10, "offset": 0}))
        is True
    )
    assert (
        asyncio.run(
            authorize_assistant_read(
                _ctx(), {"assistant_id": "fde89690-32c3-5cb8-92a9-66ce73d9514a"}
            )
        )
        is True
    )
    assert asyncio.run(authorize_assistant_read(_ctx(), {})) is False


@pytest.mark.parametrize("handler", [authorize_store_get, authorize_store_mutation])
@pytest.mark.parametrize(
    "namespace,allowed",
    [
        (("owner_opaque_01", "preferences"), True),
        (("owner_opaque_01", "reports", "report-1"), True),
        (("local-owner-v1", "sessions"), True),
        (("local-owner-v1", "session-library-views"), True),
        (("other", "preferences"), False),
        (("owner_opaque_01", "unknown"), False),
        (("app", "v1", "cross-session-memory"), False),
        (("app", "v1", "documentation-retrieval"), False),
        (("app", "v1", "phase5-audit"), False),
        ((), False),
    ],
)
def test_raw_store_only_preserves_explicit_legacy_access(handler, namespace, allowed):
    value = {"namespace": namespace}
    assert _authorized_legacy_namespace(_ctx(), value) is allowed
    assert asyncio.run(handler(_ctx(), value)) is allowed


def _search(namespace, **overrides):
    value = {
        "namespace": namespace,
        "filter": None,
        "limit": 10,
        "offset": 0,
        "query": None,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "logical,record",
    [
        (DOCUMENTATION_DOCUMENTS_NAMESPACE, "document"),
        (DOCUMENTATION_FRAGMENTS_NAMESPACE, "fragment"),
    ],
)
def test_phase5_logical_store_get_is_denied_without_rewrite(logical, record):
    value = {"namespace": logical, "key": "record-1"}
    with patch.dict(os.environ, _ENV, clear=False):
        assert asyncio.run(authorize_store_get(_ctx(), value)) is False
    assert value["namespace"] == logical
    assert record in {"document", "fragment"}


@pytest.mark.parametrize(
    "value",
    [
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, limit=21),
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, limit=0),
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, offset=1),
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, query="not metadata"),
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, filter={"owner_id": "other"}),
        _search(DOCUMENTATION_DOCUMENTS_NAMESPACE, filter={"tags": ["guide"]}),
        _search(DOCUMENTATION_FRAGMENTS_NAMESPACE, query="x" * 4097),
        _search(DOCUMENTATION_FRAGMENTS_NAMESPACE, query=""),
        _search(DOCUMENTATION_FRAGMENTS_NAMESPACE, query="bounded", filter={}),
    ],
)
def test_documentation_store_search_rejects_bounds_and_cross_mode_inputs(value):
    original_namespace = value["namespace"]
    with patch.dict(os.environ, _ENV, clear=False):
        assert asyncio.run(authorize_store_search(_ctx(), value)) is False
    assert value["namespace"] == original_namespace


def test_document_metadata_and_fragment_semantic_direct_store_search_are_denied():
    documents = _search(
        DOCUMENTATION_DOCUMENTS_NAMESPACE,
        filter={"source_type": "public-https", "tags": {"$contains": "guide"}},
        limit=20,
    )
    fragments = _search(
        DOCUMENTATION_FRAGMENTS_NAMESPACE,
        query="native semantic query",
        limit=20,
    )
    with patch.dict(os.environ, _ENV, clear=False):
        assert asyncio.run(authorize_store_search(_ctx(), documents)) is False
        assert asyncio.run(authorize_store_search(_ctx(), fragments)) is False
    assert documents["namespace"] == DOCUMENTATION_DOCUMENTS_NAMESPACE
    assert fragments["namespace"] == DOCUMENTATION_FRAGMENTS_NAMESPACE


@pytest.mark.parametrize(
    "namespace",
    [
        ("other-corpus", "documents"),
        ("installation-docs", "audits"),
        ("installation-docs", "memory"),
        ("installation-docs", "documents", "owner_opaque_01"),
        (
            "app",
            "v1",
            "documentation-retrieval",
            "tenant:tenant_opaque_01",
            "trust:local-installation-v1",
            "owner:person:owner_opaque_01",
            "corpus:installation-docs",
            "record:document",
        ),
    ],
)
def test_documentation_store_rejects_wrong_corpus_record_and_internal_scope(namespace):
    value = {"namespace": namespace, "key": "record-1"}
    with patch.dict(os.environ, _ENV, clear=False):
        assert asyncio.run(authorize_store_get(_ctx(), value)) is False
    assert value["namespace"] == namespace


def test_documentation_store_requires_server_configured_owner_scope():
    owner_value = {"namespace": DOCUMENTATION_DOCUMENTS_NAMESPACE, "key": "doc-1"}
    tenant_value = _search(DOCUMENTATION_FRAGMENTS_NAMESPACE, query="bounded")
    with patch.dict(os.environ, _ENV, clear=False):
        assert (
            asyncio.run(authorize_store_get(_ctx(owner="other"), owner_value)) is False
        )
        assert (
            asyncio.run(authorize_store_search(_ctx(tenant="other"), tenant_value))
            is False
        )


def test_phase5_store_api_is_read_only_and_namespace_listing_stays_denied():
    for namespace in (
        DOCUMENTATION_DOCUMENTS_NAMESPACE,
        DOCUMENTATION_FRAGMENTS_NAMESPACE,
    ):
        value = {"namespace": namespace, "key": "record-1", "value": {}}
        assert asyncio.run(authorize_store_mutation(_ctx(), value)) is False
    assert asyncio.run(deny_store_namespace_listing(_ctx(), {})) is False


def test_legacy_store_search_rule_is_unchanged_and_not_rewritten():
    value = _search(("owner_opaque_01", "preferences"), query="legacy", offset=999)
    assert asyncio.run(authorize_store_search(_ctx(), value)) is True
    assert value["namespace"] == ("owner_opaque_01", "preferences")
