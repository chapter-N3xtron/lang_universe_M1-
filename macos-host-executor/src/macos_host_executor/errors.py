"""Stable fail-closed error types."""


class ExecutorError(Exception):
    """Base error safe to map to a bounded API response."""


class PolicyDeniedError(ExecutorError):
    """The request is outside the exact trusted policy."""


class StateConflictError(ExecutorError):
    """The durable lifecycle does not permit the requested transition."""


class InputChangedError(PolicyDeniedError):
    """An approval-bound mutable input changed."""
