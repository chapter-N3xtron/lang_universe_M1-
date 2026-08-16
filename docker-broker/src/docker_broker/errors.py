from __future__ import annotations


class BrokerError(Exception):
    status_code = 400
    code = "broker_error"


class PolicyError(BrokerError):
    status_code = 422
    code = "policy_rejected"


class ApprovalRejected(BrokerError):
    status_code = 403
    code = "approval_rejected"


class LeaseError(BrokerError):
    status_code = 403
    code = "lease_invalid"


class ConflictError(BrokerError):
    status_code = 409
    code = "scope_conflict"


class OperationError(BrokerError):
    status_code = 502
    code = "docker_operation_failed"


class AuthenticationError(BrokerError):
    status_code = 401
    code = "client_authentication_failed"


class RateLimitError(BrokerError):
    status_code = 429
    code = "activation_rate_limited"
