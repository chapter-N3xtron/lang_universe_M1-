"""Tests for Jasper tools (list_todos, read_file, web_search, read_url)."""

import os
import re
import tempfile
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src import jasper_tools as jt
from src.jasper_tools import (
    agent_evidence,
    agent_workspace,
    draw_concept_map,
    read_file,
)


def test_read_file_valid():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "hello.txt")
        with open(file_path, "w") as f:
            f.write("Hello, world!")

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert result == "Hello, world!"


def test_read_file_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": "../../etc/passwd"})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert "Access denied" in result
    assert "outside the workspace" in result


def test_read_file_symlink_escaping_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "outside.txt")
        with open(target, "w") as f:
            f.write("secret")

        link = os.path.join(tmp, "link.txt")
        os.symlink(target, link)

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": link})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert result == "secret"


def test_read_file_binary_extension_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "image.png")
        with open(file_path, "wb") as f:
            f.write(b"PNG fake content")

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert "Cannot read binary file" in result


def test_read_file_oversized_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "large.txt")
        with open(file_path, "w") as f:
            f.write("x" * (100 * 1024 + 1))

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert "File too large" in result
    assert "100KB" in result


def test_read_file_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "nonexistent.txt")
        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert "File not found" in result


def test_read_file_relative_path_resolves_to_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        subdir = os.path.join(tmp, "subdir")
        os.makedirs(subdir)
        file_path = os.path.join(subdir, "note.txt")
        with open(file_path, "w") as f:
            f.write("relative path works")

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": "subdir/note.txt"})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert result == "relative path works"


def test_read_file_no_workspace():
    if "AGENT_WORKSPACE" in os.environ:
        del os.environ["AGENT_WORKSPACE"]

    result = read_file.invoke({"file_path": "test.txt"})
    assert "AGENT_WORKSPACE" in result


def test_read_file_workspace_context_is_scoped():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "scoped.txt")
        with open(file_path, "w") as f:
            f.write("scoped workspace")

        with agent_workspace(tmp):
            assert read_file.invoke({"file_path": "scoped.txt"}) == "scoped workspace"

        result = read_file.invoke({"file_path": "scoped.txt"})
        assert "AGENT_WORKSPACE" in result


def test_read_file_blocks_credentials():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, ".env")
        with open(file_path, "w") as f:
            f.write("SECRET=do-not-return")

        os.environ["AGENT_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["AGENT_WORKSPACE"]

    assert "Access denied" in result
    assert "do-not-return" not in result


def test_draw_concept_map_returns_validated_artifact():
    with agent_evidence("Input flows to output"):
        result = draw_concept_map.invoke(
            {
                "title": "Request flow",
                "alt_text": "Input flows to output.",
                "grounding_kind": "user_input",
                "nodes": [
                    {
                        "id": "input",
                        "label": "Input",
                        "kind": "input",
                        "narration": "The input starts the flow.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                    {
                        "id": "output",
                        "label": "Output",
                        "kind": "output",
                        "narration": "The output ends the flow.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                ],
                "narration_order": ["input", "output"],
                "edges": [
                    {
                        "source": "input",
                        "target": "output",
                        "relation": "flows_to",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    }
                ],
                "direction": "left_to_right",
            }
        )

    assert result["renderer"] == "react_flow"
    assert result["payload"]["edges"][0]["target"] == "output"


def test_draw_concept_map_rejects_disconnected_islands():
    with (
        agent_evidence("A broken flow"),
        pytest.raises(ValidationError, match="single connected graph"),
    ):
        draw_concept_map.invoke(
            {
                "title": "Broken request flow",
                "alt_text": "Two disconnected flows.",
                "grounding_kind": "user_input",
                "nodes": [
                    {
                        "id": "ui",
                        "label": "UI",
                        "narration": "The UI receives input.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                    {
                        "id": "langgraph",
                        "label": "LangGraph",
                        "narration": "LangGraph orchestrates the flow.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                    {
                        "id": "jasper",
                        "label": "Jasper",
                        "narration": "Jasper handles the request.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                    {
                        "id": "tools",
                        "label": "Tools",
                        "narration": "Tools perform actions.",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                ],
                "narration_order": ["ui", "langgraph", "jasper", "tools"],
                "edges": [
                    {
                        "source": "ui",
                        "target": "langgraph",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                    {
                        "source": "jasper",
                        "target": "tools",
                        "claim_status": "user_defined",
                        "evidence_refs": ["user-input"],
                    },
                ],
            }
        )


def test_draw_concept_map_rejects_unobserved_evidence():
    with (
        agent_evidence("Draw a claim"),
        pytest.raises(ValueError, match="not returned by a trusted tool"),
    ):
        draw_concept_map.invoke(
            {
                "title": "Unsupported",
                "alt_text": "An unsupported claim.",
                "grounding_kind": "mixed",
                "nodes": [
                    {
                        "id": "claim",
                        "label": "Claim",
                        "narration": "This claim has no trusted evidence.",
                        "claim_status": "inferred",
                        "evidence_refs": ["invented-source"],
                    }
                ],
                "narration_order": ["claim"],
                "edges": [],
            }
        )


def test_repo_map_uses_evidence_registered_by_read_file():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "flow.py")
        with open(file_path, "w") as file:
            file.write("def entrypoint():\n    return 'response'\n")

        with agent_workspace(tmp), agent_evidence("Visualize this repo"):
            file_result = read_file.invoke({"file_path": "flow.py"})
            evidence_match = re.search(r'id="([^"]+)"', file_result)
            assert evidence_match is not None
            source_id = evidence_match.group(1)
            artifact = draw_concept_map.invoke(
                {
                    "title": "Repository flow",
                    "alt_text": "The entrypoint returns a response.",
                    "grounding_kind": "repo",
                    "nodes": [
                        {
                            "id": "entrypoint",
                            "label": "entrypoint",
                            "kind": "code",
                            "narration": "The entrypoint is defined in flow.py.",
                            "claim_status": "observed",
                            "evidence_refs": [source_id],
                        },
                        {
                            "id": "response",
                            "label": "response",
                            "kind": "output",
                            "narration": "The function returns a response.",
                            "claim_status": "observed",
                            "evidence_refs": [source_id],
                        },
                    ],
                    "narration_order": ["entrypoint", "response"],
                    "edges": [
                        {
                            "source": "entrypoint",
                            "target": "response",
                            "relation": "flows_to",
                            "claim_status": "observed",
                            "evidence_refs": [source_id],
                        }
                    ],
                }
            )

    assert artifact["payload"]["grounding_kind"] == "repo"
    assert artifact["payload"]["sources"][0]["locator"] == "flow.py"


def test_web_search_no_api_key():
    if "TAVILY_API_KEY" in os.environ:
        del os.environ["TAVILY_API_KEY"]

    result = jt.web_search.invoke({"query": "test"})
    assert "TAVILY_API_KEY" in result
    assert "not configured" in result


@patch.object(jt, "TavilySearch")
def test_web_search_success(mock_tavily):
    os.environ["TAVILY_API_KEY"] = "tvly-test-key"
    mock_instance = Mock()
    mock_instance.invoke.return_value = {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com",
                "content": "Some content about the query.",
            }
        ]
    }
    mock_tavily.return_value = mock_instance

    try:
        with agent_evidence("Research the latest news"):
            result = jt.web_search.invoke({"query": "latest news"})
    finally:
        del os.environ["TAVILY_API_KEY"]

    assert "Test Result" in result
    assert "https://example.com" in result
    assert "Some content about the query" in result
    assert "Evidence: web-" in result


@patch.object(jt, "TavilySearch")
def test_web_search_no_results(mock_tavily):
    os.environ["TAVILY_API_KEY"] = "tvly-test-key"
    mock_instance = Mock()
    mock_instance.invoke.return_value = {"results": []}
    mock_tavily.return_value = mock_instance

    try:
        result = jt.web_search.invoke({"query": "nothing"})
    finally:
        del os.environ["TAVILY_API_KEY"]

    assert result == "No results found."


@patch.object(jt.httpx, "get")
def test_read_url_success(mock_get):
    mock_response = Mock()
    mock_response.text = "# Hello\n\nThis is a test page."
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = jt.read_url.invoke({"url": "https://example.com"})
    assert "# Hello" in result
    assert "test page" in result


@patch.object(jt.httpx, "get")
def test_read_url_invalid_scheme(mock_get):
    result = jt.read_url.invoke({"url": "ftp://example.com"})
    assert "Error" in result
    mock_get.assert_not_called()


@patch.object(jt.httpx, "get")
def test_read_url_http_error(mock_get):
    mock_get.side_effect = __import__("httpx").HTTPStatusError(
        "404", request=Mock(), response=Mock(status_code=404)
    )

    result = jt.read_url.invoke({"url": "https://example.com/404"})
    assert "HTTP error 404" in result


@patch.object(jt.httpx, "get")
def test_read_url_truncates(mock_get):
    mock_response = Mock()
    mock_response.text = "x" * 60000
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = jt.read_url.invoke({"url": "https://example.com"})
    assert len(result) <= 50050
    assert "truncated" in result
