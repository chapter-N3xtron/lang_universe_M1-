"""Direct local Ollama client fallback for models OpenCode CLI can't route."""

import json
import os
from typing import List, Optional

import requests


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def list_ollama_models(timeout: int = 5) -> List[dict]:
    """Return Ollama's /api/tags model list."""
    try:
        resp = requests.get(f"{_ollama_base_url()}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])
    except Exception:
        return []


def chat_ollama(
    message: str,
    model: str,
    history: Optional[List[dict]] = None,
    system: Optional[str] = None,
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
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
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
