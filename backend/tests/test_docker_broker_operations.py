"""Focused contract tests for the Coder-facing Docker broker result tool."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.docker_broker_operations import (
    DockerBrokerConfig,
    DockerBrokerOperationError,
    DockerBrokerResultClient,
    DockerOperationPlan,
    canonical_json_bytes,
    create_request_docker_compose_operation_tool,
    load_docker_broker_config,
    operation_digest,
    validate_and_sanitize_result,
)


def _plan() -> DockerOperationPlan:
    return DockerOperationPlan.model_validate_json(
        json.dumps(
            {
                "request_id": "req-1",
                "project_directory": ".",
                "compose_files": ["docker-compose.yml"],
                "operation": "up",
                "services": [],
                "profiles": [],
            }
        )
    )


def test_plan_schema_is_strict_and_tool_exposes_only_plan_fields(tmp_path):
    plan = _plan()
    assert plan.model_dump(mode="json")["compose_files"] == ["docker-compose.yml"]
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate_json(
            json.dumps({**plan.model_dump(mode="json"), "workspace": str(tmp_path)})
        )
    without_project_directory = plan.model_dump(mode="json")
    without_project_directory.pop("project_directory")
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate_json(json.dumps(without_project_directory))
    with pytest.raises(ValidationError):
        DockerOperationPlan.model_validate_json(
            json.dumps({**plan.model_dump(mode="json"), "compose_files": ["a", "b"]})
        )

    tool = create_request_docker_compose_operation_tool(
        DockerBrokerConfig("http://127.0.0.1:8766"), tmp_path
    )
    assert tool.name == "request_docker_compose_operation"
    assert set(tool.args_schema.model_fields) == {
        "request_id",
        "project_directory",
        "compose_files",
        "operation",
        "services",
        "profiles",
    }
    parsed = tool._parse_input(plan.model_dump(mode="json"), None)
    assert parsed["compose_files"] == ("docker-compose.yml",)


def test_digest_golden_vector_binds_complete_plan_and_canonical_workspace():
    plan = _plan()
    assert plan.digest == "e3671671c30281f2a051b42c01a4c1aaefed49651ee4f4cc008ed5f4df7334d5"
    assert operation_digest(plan, "/Volumes/Storage/example") == (
        "3c8d437b9aa3494205727c214cb028fe96d40a866e746870fb4b96b89e7c9b2a"
    )


def test_result_client_is_get_only_and_bounded():
    captured = {}

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, amount):
            captured["read"] = amount
            return b"{}"

    class Opener:
        def open(self, request, timeout):
            captured["method"] = request.get_method()
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return Response()

    client = DockerBrokerResultClient("http://127.0.0.1:8766")
    client._opener = Opener()
    digest = "a" * 64
    assert client.fetch(digest) == b"{}"
    assert captured == {
        "method": "GET",
        "url": f"http://127.0.0.1:8766/v1/coder/results/{digest}",
        "headers": {"Accept": "application/json"},
        "timeout": 5.0,
        "read": 64 * 1024 + 1,
    }

    class LargeResponse(Response):
        headers = {"Content-Length": str(64 * 1024 + 1)}

    client._opener = SimpleNamespace(open=lambda *_args, **_kwargs: LargeResponse())
    with pytest.raises(DockerBrokerOperationError, match="result_too_large"):
        client.fetch(digest)


def test_terminal_result_is_digest_checked_sanitized_and_canonical(tmp_path):
    plan = _plan()
    digest = operation_digest(plan, tmp_path)
    body = canonical_json_bytes(
        {
            "operation_digest": digest,
            "plan_digest": plan.digest,
            "state": "succeeded",
            "result": {
                "message": "password=hunter2",
                "token": "not returned",
                "services": ["api"],
            },
        }
    )
    result = validate_and_sanitize_result(body, plan, tmp_path)
    assert result == canonical_json_bytes(json.loads(result)).decode()
    assert "hunter2" not in result
    assert "not returned" not in result
    assert "[REDACTED]" in result

    nonterminal = json.loads(body)
    nonterminal["state"] = "running"
    with pytest.raises(DockerBrokerOperationError, match="invalid_docker_broker_result"):
        validate_and_sanitize_result(canonical_json_bytes(nonterminal), plan, tmp_path)


def test_invalid_or_partial_endpoint_config_fails_closed(monkeypatch):
    for value in (
        None,
        "host.docker.internal:8766",
        "http://host.docker.internal",
        "http://user@host.docker.internal:8766",
        "http://host.docker.internal:8766/path",
        "http://host.docker.internal:8766?token=x",
    ):
        if value is None:
            monkeypatch.delenv("DOCKER_BROKER_URL", raising=False)
        else:
            monkeypatch.setenv("DOCKER_BROKER_URL", value)
        assert load_docker_broker_config() is None

    monkeypatch.setenv(
        "DOCKER_BROKER_URL", "http://host.docker.internal:8766"
    )
    assert load_docker_broker_config() == DockerBrokerConfig(
        "http://host.docker.internal:8766"
    )
