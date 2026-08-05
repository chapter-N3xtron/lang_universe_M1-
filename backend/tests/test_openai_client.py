from types import SimpleNamespace


def test_openai_model_discovery_returns_all_accessible_gpt_variants(monkeypatch):
    import openai

    from src.openai_client import list_openai_gpt_models

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda: SimpleNamespace(
            models=SimpleNamespace(
                list=lambda: SimpleNamespace(
                    data=[
                        SimpleNamespace(id="gpt-5.6-sol"),
                        SimpleNamespace(id="gpt-5.6-terra"),
                        SimpleNamespace(id="text-embedding-3-small"),
                    ]
                )
            )
        ),
    )

    assert list_openai_gpt_models() == [
        {
            "id": "openai/gpt-5.6-sol",
            "name": "gpt-5.6-sol",
            "provider": "openai",
        },
        {
            "id": "openai/gpt-5.6-terra",
            "name": "gpt-5.6-terra",
            "provider": "openai",
        },
    ]


def test_openai_model_discovery_is_empty_without_key(monkeypatch):
    from src.openai_client import list_openai_gpt_models

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert list_openai_gpt_models() == []


def test_openai_model_discovery_fails_closed(monkeypatch):
    import openai

    from src.openai_client import list_openai_gpt_models

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    assert list_openai_gpt_models() == []
