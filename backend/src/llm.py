import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://ollama.com")
API_KEY = os.getenv("LLM_API_KEY", "")
CHAT_UI_MODEL = os.getenv("CHAT_UI_MODEL", "glm-5.2")
CODING_MODEL = os.getenv("CODING_MODEL", "ollama/qwen3.5:27b")
CODING_MODEL_PROVIDER = os.getenv("CODING_MODEL_PROVIDER", "ollama")
CODING_OLLAMA_BASE_URL = os.getenv(
    "CODING_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
)
CODING_OLLAMA_CLOUD_BASE_URL = os.getenv(
    "CODING_OLLAMA_CLOUD_BASE_URL", "https://ollama.com"
)


def _strip_provider_prefix(model_name: str) -> str:
    """Strip any 'provider/' prefix from model env vars."""
    if "/" in model_name:
        return model_name.split("/", 1)[1]
    return model_name


def get_llm(model_name: str = None):
    """Get the general chat model via the Ollama-compatible API."""
    model = model_name or CHAT_UI_MODEL
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


def get_chat_ui_llm():
    """Get LLM for Chat UI (GLM)"""
    return get_llm()


def _coding_provider_and_model(model_name: str | None) -> tuple[str, str]:
    selected = model_name or CODING_MODEL
    for prefix, provider in (
        ("ollama-cloud/", "ollama-cloud"),
        ("ollama/", "ollama"),
        ("huggingface/", "huggingface"),
        ("hf/", "huggingface"),
    ):
        if selected.startswith(prefix):
            return provider, selected[len(prefix) :]
    if selected.startswith("ollama:"):
        return "ollama", selected[len("ollama:") :]
    return CODING_MODEL_PROVIDER, selected


def get_coding_llm(model_name: str | None = None):
    """Create the selected coding model without logging credential values."""
    provider, model = _coding_provider_and_model(model_name)
    if provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

        endpoint = HuggingFaceEndpoint(
            repo_id=model,
            task="text-generation",
            max_new_tokens=1024,
            temperature=0.01,
            streaming=True,
        )
        return ChatHuggingFace(llm=endpoint, model_id=model)

    if provider not in {"ollama", "ollama-cloud"}:
        raise ValueError(f"Unsupported coding model provider: {provider}")

    if provider == "ollama-cloud":
        base_url = CODING_OLLAMA_CLOUD_BASE_URL
        api_key = os.getenv("OLLAMA_API_KEY", "") or API_KEY
    else:
        base_url = CODING_OLLAMA_BASE_URL
        api_key = ""

    client_kwargs = {}
    if api_key:
        client_kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
    return ChatOllama(
        model=model,
        base_url=base_url,
        client_kwargs=client_kwargs,
        temperature=0,
        num_ctx=int(os.getenv("CODING_OLLAMA_NUM_CTX", "8192")),
        num_predict=int(os.getenv("CODING_OLLAMA_NUM_PREDICT", "256")),
    )
