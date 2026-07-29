"""Tests for Jasper tools (list_todos, read_file, web_search, read_url)."""

import os
import tempfile
from unittest.mock import patch, Mock

from src import jasper_tools as jt
from src.jasper_tools import read_file, web_search, read_url


def test_read_file_valid():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "hello.txt")
        with open(file_path, "w") as f:
            f.write("Hello, world!")

        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert result == "Hello, world!"


def test_read_file_path_traversal_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": "../../etc/passwd"})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert "Access denied" in result
    assert "outside the workspace" in result


def test_read_file_symlink_escaping_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "outside.txt")
        with open(target, "w") as f:
            f.write("secret")

        link = os.path.join(tmp, "link.txt")
        os.symlink(target, link)

        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": link})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert result == "secret"


def test_read_file_binary_extension_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "image.png")
        with open(file_path, "wb") as f:
            f.write(b"PNG fake content")

        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert "Cannot read binary file" in result


def test_read_file_oversized_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "large.txt")
        with open(file_path, "w") as f:
            f.write("x" * (100 * 1024 + 1))

        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert "File too large" in result
    assert "100KB" in result


def test_read_file_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = os.path.join(tmp, "nonexistent.txt")
        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": file_path})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert "File not found" in result


def test_read_file_relative_path_resolves_to_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        subdir = os.path.join(tmp, "subdir")
        os.makedirs(subdir)
        file_path = os.path.join(subdir, "note.txt")
        with open(file_path, "w") as f:
            f.write("relative path works")

        os.environ["OPENCODE_WORKSPACE"] = tmp
        try:
            result = read_file.invoke({"file_path": "subdir/note.txt"})
        finally:
            del os.environ["OPENCODE_WORKSPACE"]

    assert result == "relative path works"


def test_read_file_no_workspace():
    if "OPENCODE_WORKSPACE" in os.environ:
        del os.environ["OPENCODE_WORKSPACE"]

    result = read_file.invoke({"file_path": "test.txt"})
    assert "OPENCODE_WORKSPACE" in result


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
            {"title": "Test Result", "url": "https://example.com", "content": "Some content about the query."}
        ]
    }
    mock_tavily.return_value = mock_instance

    try:
        result = jt.web_search.invoke({"query": "latest news"})
    finally:
        del os.environ["TAVILY_API_KEY"]

    assert "Test Result" in result
    assert "https://example.com" in result
    assert "Some content about the query" in result


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
    mock_get.side_effect = __import__("httpx").HTTPStatusError("404", request=Mock(), response=Mock(status_code=404))

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
