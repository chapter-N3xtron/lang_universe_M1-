import importlib
import sys
from unittest.mock import patch


def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def test_magic_coder_subgraph_returns_assistant_message():
    _clear_src_modules()
    with patch("src.magic_coder_graph.run_magic_coder") as mock_run:
        mock_run.return_value = {
            "success": True,
            "text": "Here is the file listing.",
            "error": None,
        }

        app_module = importlib.import_module("src.magic_coder_graph")
        app = app_module.create_magic_coder_graph()

        result = app.invoke(
            {
                "messages": [{"role": "user", "content": "List files"}],
                "workspace": "/tmp",
                "mode": "live",
                "model": None,
            }
        )

    assert len(result["messages"]) >= 1
    assert result["messages"][-1]["role"] == "assistant"
    assert "file listing" in result["messages"][-1]["content"]
    assert result["code_response"] == result["messages"][-1]["content"]


def test_magic_coder_subgraph_handles_error():
    _clear_src_modules()
    with patch("src.magic_coder_graph.run_magic_coder") as mock_run:
        mock_run.return_value = {
            "success": False,
            "text": "",
            "error": "Model unavailable",
        }

        app_module = importlib.import_module("src.magic_coder_graph")
        app = app_module.create_magic_coder_graph()

        result = app.invoke(
            {
                "messages": [{"role": "user", "content": "Do something"}],
                "workspace": "/tmp",
                "mode": "live",
                "model": None,
            }
        )

    assert len(result["messages"]) >= 1
    assert "Magic Coder error" in result["messages"][-1]["content"]


def test_magic_coder_subgraph_passes_history():
    _clear_src_modules()
    with patch("src.magic_coder_graph.run_magic_coder") as mock_run:
        mock_run.return_value = {
            "success": True,
            "text": "Final answer.",
            "error": None,
        }

        app_module = importlib.import_module("src.magic_coder_graph")
        app = app_module.create_magic_coder_graph()

        app.invoke(
            {
                "messages": [
                    {"role": "user", "content": "First query"},
                    {"role": "assistant", "content": "First response"},
                    {"role": "user", "content": "Second query"},
                ],
                "workspace": "/tmp",
                "mode": "live",
                "model": None,
            }
        )

    assert mock_run.call_count >= 1
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs["message"] == "Second query"
    assert len(call_kwargs["history"]) >= 2
