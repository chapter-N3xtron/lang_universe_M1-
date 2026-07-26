import importlib
import sys
from unittest.mock import MagicMock, patch


def _make_llm_response(content: str):
    mock = MagicMock()
    mock.content = content
    return mock


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_jasper_subgraph_produces_assistant_message():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("Hello! I can help with daily tasks.")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "What can you do?"}],
        })

    assert len(result["messages"]) >= 1
    assert result["messages"][-1]["role"] == "assistant"
    assert "Hello" in result["messages"][-1]["content"]
    assert result["jasper_response"] == result["messages"][-1]["content"]


def test_jasper_subgraph_handles_llm_error():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM unavailable")

    _clear_src_modules()
    with patch("src.llm.ChatOllama", return_value=mock_llm):
        app_module = importlib.import_module("src.jasper_agent")
        app = app_module.create_jasper_graph()

        result = app.invoke({
            "messages": [{"role": "user", "content": "Test error handling"}],
        })

    assert len(result["messages"]) >= 1
    assert result["messages"][-1]["role"] == "assistant"
    assert "I'm Jasper" in result["messages"][-1]["content"]


def test_jasper_subgraph_full_conversation_history():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _make_llm_response("Continuing our conversation.")

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
    assert result["messages"][-1]["role"] == "assistant"
