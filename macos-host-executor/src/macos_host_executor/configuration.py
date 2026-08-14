"""Fail-closed production configuration loaded only from explicit host inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .confirmation import AgentServerPendingInterruptChecker, ConfirmationHelper
from .policy import ActionPolicy, PolicyConfig


class ConfigurationError(ValueError):
    """Production authority is incomplete or invalid."""


@dataclass(frozen=True)
class ProductionConfiguration:
    policy: ActionPolicy
    pending: AgentServerPendingInterruptChecker
    confirmation: ConfirmationHelper
    state_directory: Path


def load_production_configuration(
    *,
    policy_json: Path | None,
    agent_server_url: str | None,
    confirmation_helper: Path | None,
    state_directory: Path | None,
) -> ProductionConfiguration:
    """Load every required authority input, or refuse to configure any authority."""
    values = {
        "policy JSON": policy_json,
        "Agent Server URL": agent_server_url,
        "confirmation helper": confirmation_helper,
        "state directory": state_directory,
    }
    missing = tuple(name for name, value in values.items() if value is None)
    if missing:
        raise ConfigurationError(
            "deny-all: missing required production configuration: " + ", ".join(missing)
        )
    assert policy_json is not None
    assert agent_server_url is not None
    assert confirmation_helper is not None
    assert state_directory is not None
    try:
        policy_path = policy_json.expanduser().resolve(strict=True)
        if not policy_path.is_file():
            raise ConfigurationError("policy must be a regular file")
        policy = PolicyConfig.model_validate_json(
            policy_path.read_text(encoding="utf-8")
        )
        state = state_directory.expanduser().resolve()
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        state.chmod(0o700)
        pending = AgentServerPendingInterruptChecker(agent_server_url)
        confirmation = ConfirmationHelper(confirmation_helper.expanduser())
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(
            f"deny-all: invalid production configuration: {exc}"
        ) from exc
    return ProductionConfiguration(
        policy=ActionPolicy(policy),
        pending=pending,
        confirmation=confirmation,
        state_directory=state,
    )
