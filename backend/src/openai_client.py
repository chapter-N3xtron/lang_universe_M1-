"""OpenAI model discovery for the authenticated UI model picker."""

from __future__ import annotations

import os


def list_openai_gpt_models() -> list[dict[str, str]]:
    """Return every GPT model visible to the configured OpenAI API key."""

    if not os.getenv("OPENAI_API_KEY"):
        return []
    try:
        from openai import OpenAI

        model_ids = {
            model.id
            for model in OpenAI().models.list().data
            if model.id.startswith("gpt-")
        }
    except Exception:
        return []
    return [
        {"id": f"openai/{model_id}", "name": model_id, "provider": "openai"}
        for model_id in sorted(model_ids)
    ]
