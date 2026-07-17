import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://ollama.com")
API_KEY = os.getenv("LLM_API_KEY", "")
CHAT_UI_MODEL = os.getenv("CHAT_UI_MODEL", "glm-5.2")
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "qwen3.5:397b")


def _strip_provider_prefix(model_name: str) -> str:
    """Strip any 'provider/' prefix from model env vars."""
    if "/" in model_name:
        return model_name.split("/", 1)[1]
    return model_name


def get_llm(model_name: str = None, for_opencode: bool = False):
    """
    Get LLM via Ollama Cloud native API.

    Args:
        model_name: Override model name
        for_opencode: Use OpenCode coding model
    """
    model = model_name or (OPENCODE_MODEL if for_opencode else CHAT_UI_MODEL)
    model = _strip_provider_prefix(model)

    client_kwargs = {}
    if API_KEY:
        client_kwargs["headers"] = {"Authorization": f"Bearer {API_KEY}"}

    return ChatOllama(
        model=model,
        base_url=BASE_URL,
        client_kwargs=client_kwargs,
        temperature=0.7,
    )


def get_opencode_llm():
    """Get LLM for OpenCode CLI agent (Qwen for coding)"""
    return get_llm(for_opencode=True)


def get_chat_ui_llm():
    """Get LLM for Chat UI (GLM)"""
    return get_llm(for_opencode=False)
