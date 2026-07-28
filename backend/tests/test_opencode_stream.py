"""Tests for async run_opencode_stream in backend/src/opencode_cli.py."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_opencode_stream_yields_text_and_complete():
    from src.opencode_cli import run_opencode_stream

    jsonl_lines = [
        b'{"type":"text","sessionID":"sess-abc","part":{"text":"hello"}}\n',
        b'{"type":"text","sessionID":"sess-abc","part":{"text":" world"}}\n',
    ]

    mock_process = AsyncMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.__aiter__.return_value = iter(jsonl_lines)
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.returncode = 0
    mock_process.stderr = AsyncMock()
    mock_process.stderr.__aiter__.return_value = iter([])

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        events = []
        async for event in run_opencode_stream(
            message="test", title="test", workspace="/tmp", model="anthropic/claude-sonnet-4"
        ):
            events.append(event)

    assert len(events) == 3
    assert events[0] == {"type": "text", "text": "hello", "session_id": "sess-abc"}
    assert events[1] == {"type": "text", "text": " world", "session_id": "sess-abc"}
    assert events[2]["type"] == "complete"
    assert events[2]["session_id"] == "sess-abc"
    assert events[2]["text"] == "hello\n\n world"


@pytest.mark.asyncio
async def test_run_opencode_stream_handles_empty_lines():
    from src.opencode_cli import run_opencode_stream

    jsonl_lines = [
        b'{"type":"text","part":{"text":"hello"}}\n',
        b"\n",
    ]

    mock_process = AsyncMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.__aiter__.return_value = iter(jsonl_lines)
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.returncode = 0
    mock_process.stderr = AsyncMock()
    mock_process.stderr.__aiter__.return_value = iter([])

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        events = []
        async for event in run_opencode_stream(
            message="test", title="test", workspace="/tmp", model="anthropic/claude-sonnet-4"
        ):
            events.append(event)

    assert len(events) == 2


@pytest.mark.asyncio
async def test_run_opencode_stream_handles_error():
    from src.opencode_cli import run_opencode_stream

    mock_process = AsyncMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.__aiter__.return_value = iter([])
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.returncode = 1
    mock_process.stderr = AsyncMock()
    mock_process.stderr.__aiter__.return_value = iter([b"something went wrong\n"])

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        events = []
        async for event in run_opencode_stream(
            message="test", title="test", workspace="/tmp", model="anthropic/claude-sonnet-4"
        ):
            events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "1" in events[0]["error"]
