from __future__ import annotations

import json

import pytest

from macos_host_executor.configuration import (
    ConfigurationError,
    load_production_configuration,
)


def test_production_configuration_is_deny_all_when_incomplete(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="deny-all.*policy JSON"):
        load_production_configuration(
            policy_json=None,
            agent_server_url=None,
            confirmation_helper=None,
            state_directory=tmp_path,
        )


def test_explicit_production_configuration_loads(tmp_path) -> None:
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({}), encoding="utf-8")
    helper = tmp_path / "confirmation-helper"
    helper.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    helper.chmod(0o700)
    state = tmp_path / "state"
    loaded = load_production_configuration(
        policy_json=policy,
        agent_server_url="http://127.0.0.1:9999",
        confirmation_helper=helper,
        state_directory=state,
    )
    assert loaded.policy.config.allowed_applications == {}
    assert loaded.state_directory == state
    assert state.stat().st_mode & 0o777 == 0o700
