"""Focused configuration contracts for the Phase 5 embedding adapter."""

import json
import os
from pathlib import Path

import pytest

import src.phase5_embeddings as adapter


class RecordingAsyncOllamaClient:
    def __init__(self) -> None:
        self.call = None

    async def embed(self, model, texts, **kwargs):
        self.call = (model, texts, kwargs)
        return {"embeddings": [[0.25, 0.5]]}


def test_store_index_uses_documented_custom_embedding_function():
    config = json.loads((Path(__file__).parents[1] / "langgraph.json").read_text())

    assert config["store"]["index"] == {
        "embed": "./src/phase5_embeddings.py:aembed_texts",
        "dims": 768,
        "fields": ["content"],
    }


def test_embedding_adapter_uses_trusted_endpoint_and_zero_keep_alive():
    expected_endpoint = (
        os.getenv("OLLAMA_HOST")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    )

    assert adapter._embeddings.model == "embeddinggemma"
    assert adapter._embeddings.base_url == expected_endpoint
    assert adapter._embeddings.keep_alive == 0


@pytest.mark.asyncio
async def test_embedding_adapter_sends_zero_keep_alive_to_ollama(monkeypatch):
    client = RecordingAsyncOllamaClient()
    monkeypatch.setattr(adapter._embeddings, "_async_client", client)

    result = await adapter.aembed_texts(["synthetic text"])

    assert result == [[0.25, 0.5]]
    model, texts, kwargs = client.call
    assert model == "embeddinggemma"
    assert texts == ["synthetic text"]
    assert kwargs["keep_alive"] == 0
