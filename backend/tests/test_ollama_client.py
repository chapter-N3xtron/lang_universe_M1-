from unittest.mock import Mock, patch

from src.ollama_client import list_ollama_cloud_models


def test_cloud_models_use_existing_generic_api_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-secret")
    response = Mock()
    response.json.return_value = {"models": [{"name": "glm-5.2"}]}

    with patch("src.ollama_client.requests.get", return_value=response) as get:
        assert list_ollama_cloud_models() == [{"name": "glm-5.2"}]

    get.assert_called_once_with(
        "https://ollama.com/api/tags",
        headers={"Authorization": "Bearer test-secret"},
        timeout=5,
    )
    response.raise_for_status.assert_called_once_with()


def test_cloud_models_do_not_request_without_a_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with patch("src.ollama_client.requests.get") as get:
        assert list_ollama_cloud_models() == []

    get.assert_not_called()


def test_cloud_model_failure_is_a_safe_empty_list(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-secret")

    with patch(
        "src.ollama_client.requests.get", side_effect=RuntimeError("unavailable")
    ):
        assert list_ollama_cloud_models() == []
