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
    assert captured["client_kwargs"]["headers"]["Authorization"].startswith("Bearer ")


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


def test_agent_model_preserves_legacy_unprefixed_chat_routing(monkeypatch):
    from src import llm

    expected = SimpleNamespace()
    captured = {}

    def get_llm(model_name):
        captured["model_name"] = model_name
        return expected

    monkeypatch.setattr(llm, "get_llm", get_llm)

    assert llm.get_agent_llm("glm-5.2") is expected
    assert captured["model_name"] == "glm-5.2"


def test_agent_model_routes_explicit_provider_models(monkeypatch):
    from src import llm

    expected = SimpleNamespace()
    captured = {}

    def get_coding_llm(model_name, **kwargs):
        captured["model_name"] = model_name
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(llm, "get_coding_llm", get_coding_llm)

    for model_name in (
        "ollama/qwen3.5:27b",
        "ollama-cloud/qwen3.5:397b",
        "huggingface/org/tool-model",
        "hf/org/tool-model",
    ):
        assert llm.get_agent_llm(model_name) is expected
        assert captured["model_name"] == model_name
        assert captured["num_predict"] == 2048


def test_coding_model_keeps_the_shorter_default_generation_limit(monkeypatch):
    from src import llm

    captured = {}
    monkeypatch.setattr(
        llm,
        "ChatOllama",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )

    llm.get_coding_llm("ollama/qwen3.5:27b")

    assert captured["num_predict"] == 256
