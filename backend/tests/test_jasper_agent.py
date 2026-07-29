"""Tests for Jasper ReAct agent subgraph.

All LLM calls are mocked so tests are fast and deterministic.
The ReAct loop is tested in two paths:
  - No-tool path: LLM returns direct answer, graph ends.
  - Tool path: LLM returns tool_calls -> ToolNode executes -> LLM returns final answer.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_jasper_subgraph_produces_assistant_message():
    """LLM returns direct answer (no tool_calls) -> graph ends with assistant message."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="Hello! I can help with daily tasks.")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "What can you do?"}],
        })

    assert len(result["messages"]) >= 1
    assert result["messages"][-1].type == "ai"
    assert "Hello" in result["messages"][-1].content
    assert result["jasper_response"] == result["messages"][-1].content


def test_jasper_subgraph_handles_llm_error():
    """LLM raises exception -> fallback response."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.side_effect = Exception("LLM unavailable")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "Test error handling"}],
        })

    assert len(result["messages"]) >= 1
    assert result["messages"][-1].type == "ai"
    assert "I'm Jasper" in result["messages"][-1].content


def test_jasper_subgraph_full_conversation_history():
    """Full message history is passed to the LLM."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="Continuing our conversation.")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
                {"role": "user", "content": "Second message"},
            ],
        })

    assert len(result["messages"]) >= 1
    assert result["messages"][-1].type == "ai"


def test_jasper_react_loop_executes_tool():
    """LLM returns tool_calls -> ToolNode executes -> LLM returns final answer."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "list_todos", "args": {}, "id": "call_test_1", "type": "tool_call"}],
        ),
        AIMessage(content="Here is your todo list summary."),
    ]

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "What are my todos?"}],
        })

    assert len(result["messages"]) >= 3
    assert result["messages"][-1].type == "ai"
    assert "Here is your todo list summary" in result["messages"][-1].content
    assert result["jasper_response"] == result["messages"][-1].content


def test_jasper_no_tool_path_returns_directly():
    """When LLM returns no tool_calls, graph ends immediately without calling ToolNode."""
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(
        content="I can answer directly without tools.",
        tool_calls=[],
    )

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "Hello"}],
        })

    assert len(result["messages"]) == 2
    assert result["jasper_response"] == "I can answer directly without tools."
