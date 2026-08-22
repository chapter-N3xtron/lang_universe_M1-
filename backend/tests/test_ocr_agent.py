import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from src.chat_ui import create_chat_ui
from src.jasper_agent import transfer_to_ocr
from src import ocr_agent


def test_ocr_path_is_confined_to_workspace(tmp_path):
    document = tmp_path / "scan.pdf"
    document.write_bytes(b"pdf")
    assert ocr_agent.approved_document_path("scan.pdf", str(tmp_path)) == document
    with pytest.raises(ValueError):
        ocr_agent.approved_document_path("../scan.pdf", str(tmp_path))


def test_transfer_schema_and_command_route():
    schema = transfer_to_ocr.args_schema.model_json_schema()
    assert schema["properties"]["output_format"]["enum"] == ["markdown", "json", "structured"]
    runtime = type("Runtime", (), {
        "state": {"messages": [AIMessage(content="handoff")]},
        "tool_call_id": "call-1",
    })()
    command = transfer_to_ocr.func("read tables", "upload:x.pdf", "json", runtime=runtime)
    assert isinstance(command, Command)
    assert command.goto == "ocr"
    assert command.update["ocr_output_format"] == "json"


def test_ollama_ocr_requests_model_unload(monkeypatch, tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"image")
    response = Mock()
    response.json.return_value = {"message": {"content": "text"}}
    post = Mock(return_value=response)
    monkeypatch.setattr(ocr_agent.requests, "post", post)

    assert ocr_agent._ollama_ocr(image, "surya", "http://ollama", 12) == "text"
    payload = post.call_args.kwargs["json"]
    assert payload["keep_alive"] == 0
    assert post.call_args.kwargs["timeout"] == 12


def test_ocr_runs_surya_phase_before_glm_verification(monkeypatch, tmp_path):
    document = tmp_path / "scan.pdf"
    document.write_bytes(b"pdf")
    pages = [tmp_path / "page-1.png", tmp_path / "page-2.png"]
    monkeypatch.setattr(ocr_agent, "_docling_layout", lambda path, render: ("layout", pages))
    calls = []

    def mocked_ocr(image, model, base_url, timeout):
        calls.append(model)
        return f"{model}:{image.name}"

    monkeypatch.setattr(ocr_agent, "_ollama_ocr", mocked_ocr)
    result = ocr_agent.run_ocr("read", str(document), str(tmp_path))

    assert calls == [ocr_agent.DEFAULT_SURYA_MODEL, ocr_agent.DEFAULT_SURYA_MODEL,
                     ocr_agent.DEFAULT_GLM_MODEL, ocr_agent.DEFAULT_GLM_MODEL]
    assert result["surya"] == [f"{ocr_agent.DEFAULT_SURYA_MODEL}:page-1.png",
                                f"{ocr_agent.DEFAULT_SURYA_MODEL}:page-2.png"]
    assert result["glm_ocr"] == [f"{ocr_agent.DEFAULT_GLM_MODEL}:page-1.png",
                                  f"{ocr_agent.DEFAULT_GLM_MODEL}:page-2.png"]
    assert len(result["disagreements"]) == 2


def test_json_specialist_result_is_valid_json(monkeypatch, tmp_path):
    document = tmp_path / "scan.pdf"
    document.write_bytes(b"pdf")
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("OCR_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setattr(ocr_agent, "_docling_layout", lambda path, render: ("layout", [path]))
    monkeypatch.setattr(ocr_agent, "_ollama_ocr", lambda image, model, base, timeout: "text")
    result = ocr_agent.run_ocr("read", str(document), str(tmp_path), "json")
    assert json.loads(ocr_agent.specialist_message(result, "json"))["normalized"] == "text"


def test_graph_declares_top_level_ocr_node_and_edges():
    graph = create_chat_ui()
    assert "ocr" in graph.nodes
    assert "jasper" in graph.nodes
