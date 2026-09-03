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
    assert _coding_provider_and_model("openai/gpt-test") == (
        "openai",
        "gpt-test",
    )
    assert _coding_provider_and_model("fireworks/accounts/fireworks/models/minimax-m3") == (
        "fireworks",
        "accounts/fireworks/models/minimax-m3",
    )


def test_default_coding_model_is_gpt_5_6(monkeypatch):
    from src import llm

    monkeypatch.setattr(llm, "CODING_MODEL", "openai/gpt-5.6-luna")
    monkeypatch.setattr(llm, "CODING_MODEL_PROVIDER", "openai")

    assert llm._coding_provider_and_model(None) == ("openai", "gpt-5.6-luna")


def test_openai_model_uses_official_langchain_integration(monkeypatch):
    import langchain_openai

    from src import llm

    captured = {}
    monkeypatch.setattr(
        langchain_openai,
        "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )

    llm.get_coding_llm("openai/gpt-test")

    assert captured == {
        "model": "gpt-test",
        "use_responses_api": True,
        "model_kwargs": {"parallel_tool_calls": False},
    }


def test_fireworks_model_uses_the_documented_openai_compatible_endpoint(monkeypatch):
    import langchain_openai

    from src import llm

    captured = {}
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-secret")
    monkeypatch.setattr(llm, "FIREWORKS_BASE_URL", "https://fireworks.test/inference/v1")
    monkeypatch.setattr(
        langchain_openai,
        "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(),
    )

    llm.get_coding_llm("fireworks/accounts/fireworks/models/minimax-m3")

    assert captured == {
        "model": "accounts/fireworks/models/minimax-m3",
        "api_key": "test-secret",
        "base_url": "https://fireworks.test/inference/v1",
        "use_responses_api": False,
        "model_kwargs": {"parallel_tool_calls": False},
        "temperature": 0,
    }


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
        "openai/gpt-test",
        "fireworks/accounts/fireworks/models/minimax-m3",
        "huggingface/org/tool-model",
        "hf/org/tool-model",
    ):
        assert llm.get_agent_llm(model_name) is expected
        assert captured["model_name"] == model_name
        assert captured["num_predict"] == 2048


def test_model_list_always_contains_the_default_coder(monkeypatch):
    from src import web_server

    monkeypatch.setenv("CODING_MODEL", "openai/gpt-5.6-terra")
    monkeypatch.setenv("CODING_MODELS", "ollama/qwen3.5:27b")
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.setattr(web_server, "list_openai_gpt_models", lambda: [])
    monkeypatch.setattr(web_server, "list_ollama_cloud_models", lambda: [])
    monkeypatch.setattr(web_server, "list_ollama_models", lambda: [])

    result = web_server.list_models()

    assert result["default"] == "openai/gpt-5.6-terra"
    assert result["models"][0]["id"] == "openai/gpt-5.6-terra"


def test_model_list_includes_the_requested_fireworks_models_with_short_labels(monkeypatch):
    from src import web_server

    monkeypatch.setenv("FIREWORKS_API_KEY", "test-secret")
    monkeypatch.setattr(web_server, "list_openai_gpt_models", lambda: [])
    monkeypatch.setattr(web_server, "list_ollama_cloud_models", lambda: [])
    monkeypatch.setattr(web_server, "list_ollama_models", lambda: [])

    models = web_server.list_models()["models"]
    fireworks_models = [model for model in models if model["provider"] == "fireworks"]

    assert fireworks_models == [
        {
            "id": "fireworks/accounts/fireworks/models/minimax-m3",
            "name": "minimax-m3",
            "provider": "fireworks",
        },
        {
            "id": "fireworks/accounts/fireworks/models/gpt-oss-120b",
            "name": "gpt-oss-120b",
            "provider": "fireworks",
        },
        {
            "id": "fireworks/accounts/fireworks/models/qwen3-vl-235b-a22b-instruct",
            "name": "qwen3-vl-235b-a22b-instruct",
            "provider": "fireworks",
        },
    ]


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
