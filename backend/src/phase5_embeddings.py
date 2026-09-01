"""Local Ollama embedding adapter for the Agent Server Store index."""

import os

from langchain_ollama import OllamaEmbeddings

_OLLAMA_ENDPOINT = (
    os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
)
_embeddings = OllamaEmbeddings(
    model="embeddinggemma",
    base_url=_OLLAMA_ENDPOINT,
    keep_alive=0,
)


async def aembed_texts(texts: list[str]) -> list[list[float]]:
    """Embed Store text and unload the local model after each request."""
    return await _embeddings.aembed_documents(texts)
