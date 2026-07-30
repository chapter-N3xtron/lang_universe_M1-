"""Provider selection tests for coding models; no live credentials are used."""

from types import SimpleNamespace


def test_coding_model_prefixes_select_expected_providers():
    from src.llm import _coding_provider_and_model

    assert _coding_provider_and_model("ollama/qwen3.5:27b") == (
        "ollama",
        "qwen3.5:27b",
    )
    assert _coding_provider_and_model("ollama-cloud/qwen3.5:397b") == (
        "ollama-cloud",
        "qwen3.5:397b",
    )
    assert _coding_provider_and_model("hf/org/tool-model") == (
        "huggingface",
        "org/tool-model",
    )


def test_local_ollama_model_uses_local_endpoint_without_auth(monkeypatch):
    from src import llm

    captured = {}
    monkeypatch.setattr(
        llm,
        "ChatOllama",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(llm, "CODING_OLLAMA_BASE_URL", "http://local.test")

    llm.get_coding_llm("ollama/qwen3.5:27b")

    assert captured["model"] == "qwen3.5:27b"
    assert captured["base_url"] == "http://local.test"
    assert captured["client_kwargs"] == {}


def test_ollama_cloud_model_uses_auth_header_without_logging_value(monkeypatch):
    from src import llm

    captured = {}
    monkeypatch.setattr(
        llm,
        "ChatOllama",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(llm, "CODING_OLLAMA_CLOUD_BASE_URL", "https://cloud.test")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-secret")

    llm.get_coding_llm("ollama-cloud/qwen3.5:397b")

    assert captured["base_url"] == "https://cloud.test"
    assert captured["client_kwargs"]["headers"]["Authorization"].startswith(
        "Bearer "
    )


def test_huggingface_model_builds_chat_endpoint(monkeypatch):
    import langchain_huggingface

    from src import llm

    captured = {}

    def endpoint(**kwargs):
        captured["endpoint"] = kwargs
        return SimpleNamespace()

    def chat(**kwargs):
        captured["chat"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(langchain_huggingface, "HuggingFaceEndpoint", endpoint)
    monkeypatch.setattr(langchain_huggingface, "ChatHuggingFace", chat)

    llm.get_coding_llm("huggingface/org/tool-model")

    assert captured["endpoint"]["repo_id"] == "org/tool-model"
    assert captured["chat"]["model_id"] == "org/tool-model"
