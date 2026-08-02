from unittest.mock import Mock

import pytest
import torch

from src import kyutai_tts


def test_pocket_tts_model_is_explicitly_moved_to_cpu(monkeypatch):
    model = torch.nn.Linear(1, 1)
    to_spy = Mock(wraps=model.to)
    monkeypatch.setattr(model, "to", to_spy)
    monkeypatch.setattr(
        kyutai_tts.TTSModel,
        "load_model",
        Mock(return_value=model),
    )

    engine = kyutai_tts.PocketTTSEngine()
    engine._load_model()

    to_spy.assert_called_once_with(device=torch.device("cpu"))
    assert engine._device.type == "cpu"


def test_pocket_tts_refuses_a_model_that_remains_off_cpu(monkeypatch):
    model = Mock()
    model.parameters.return_value = iter([Mock(device=torch.device("meta"))])
    monkeypatch.setattr(
        kyutai_tts.TTSModel,
        "load_model",
        Mock(return_value=model),
    )

    engine = kyutai_tts.PocketTTSEngine()

    with pytest.raises(RuntimeError, match="must run on CPU"):
        engine._load_model()
    assert engine._model is None
