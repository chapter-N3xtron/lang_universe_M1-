"""Direct Ollama client helpers for local and cloud-hosted models."""

import os

import requests


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def list_ollama_models(timeout: int = 5) -> list[dict]:
    """Return Ollama's /api/tags model list."""
    try:
        resp = requests.get(f"{_ollama_base_url()}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])
    except Exception:
        return []


def list_ollama_cloud_models(timeout: int = 5) -> list[dict]:
    """Return models available through Ollama Cloud without exposing its key."""
    api_key = os.getenv("OLLAMA_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    if not api_key:
        return []

    base_url = os.getenv("CODING_OLLAMA_CLOUD_BASE_URL", "https://ollama.com").rstrip(
        "/"
    )
    try:
        resp = requests.get(
            f"{base_url}/api/tags",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])
    except Exception:
        return []


def chat_ollama(
    message: str,
    model: str,
    history: list[dict] | None = None,
    system: str | None = None,
    timeout: int = 300,
) -> dict:
    """
    Chat with a local Ollama model via /api/chat.

    model should be the Ollama model name without the 'ollama/' prefix.
    Returns {"success": bool, "text": str, "error": str | None}.
    """
    if model.startswith("ollama/"):
        model = model.split("/", 1)[1]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for m in history:
            messages.append(
                {"role": m.get("role", "user"), "content": m.get("content", "")}
            )
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7},
    }

    try:
        resp = requests.post(
            f"{_ollama_base_url()}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return {"success": True, "text": text, "error": None}
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "text": "",
            "error": f"Local Ollama model timed out after {timeout}s",
        }
    except Exception as e:
        return {"success": False, "text": "", "error": f"Local Ollama error: {e}"}
