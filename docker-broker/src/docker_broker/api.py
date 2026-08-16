from __future__ import annotations

import asyncio
import hmac
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from docker_broker.audit import AuditLog
from docker_broker.coder import CoderOperationManager
from docker_broker.config import Settings
from docker_broker.confirmation import NativeConfirmation
from docker_broker.errors import (
    AuthenticationError,
    BrokerError,
    LeaseError,
    RateLimitError,
)
from docker_broker.langgraph import (
    AgentServerPendingInterruptChecker,
    PendingInterruptChecker,
)
from docker_broker.leases import LeaseStore
from docker_broker.models import (
    ActivateRequest,
    ActivateResponse,
    CoderConfirmationResponse,
    CoderOperationResult,
    CoderOperationStatus,
    ComposeApplyRequest,
    ComposeApplyResponse,
    ComposeInspectRequest,
    ComposeInspectResponse,
    ComposeTarget,
    ConfirmationAttempt,
    HealthResponse,
    RevokeResponse,
    RuntimeInspectResponse,
)
from docker_broker.policy import ComposePolicy
from docker_broker.runner import DockerRunner

_MAX_REQUEST_BYTES = 65_536
_ALLOWED_HOSTS = {
    "127.0.0.1",
    "localhost",
    "[::1]",
    "host.docker.internal",
    "testserver",
}
_CORS_ORIGINS = {
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
}


def _is_public_path(path: str) -> bool:
    return (
        path in {"/health", "/v1/coder/confirmations"}
        or path.startswith(("/v1/coder/status/", "/v1/coder/results/"))
    )


def _bearer_token(value: str | None) -> str:
    if not value or not value.startswith("Bearer "):
        raise LeaseError("Docker session authority is required")
    token = value[7:].strip()
    if len(token) < 32 or len(token) > 256:
        raise LeaseError("Docker session authority is invalid")
    return token


def create_app(
    settings: Settings,
    *,
    confirmation: NativeConfirmation | None = None,
    runner: DockerRunner | None = None,
    pending_checker: PendingInterruptChecker | None = None,
) -> FastAPI:
    client_secret = settings.client_secret
    if client_secret is None or len(client_secret) < 32:
        raise ValueError("broker client authentication is not configured")
    audit = AuditLog(settings.state_directory / "audit.jsonl")
    native_confirmation = confirmation or NativeConfirmation(
        settings.osascript_path, allow_builds=settings.allow_builds
    )
    lease_store = LeaseStore(native_confirmation, audit)
    compose_policy = ComposePolicy(settings)
    docker_runner = runner or DockerRunner(settings, audit)
    checker = pending_checker or AgentServerPendingInterruptChecker(
        settings.agent_server_url
    )
    coder_operations = CoderOperationManager(
        settings, checker, lease_store, compose_policy, docker_runner
    )
    activation_attempts: deque[float] = deque()
    activation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        try:
            yield
        finally:
            await coder_operations.close()
            await docker_runner.close()

    app = FastAPI(
        title="Jasper Docker Broker",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(_CORS_ORIGINS),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
        max_age=600,
    )

    @app.middleware("http")
    async def constrain_local_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        host = request.headers.get("host", "").lower()
        host_name = host
        if host.startswith("["):
            host_name = host.split("]", 1)[0] + "]"
        elif ":" in host:
            host_name = host.rsplit(":", 1)[0]
        origin = request.headers.get("origin")
        public = _is_public_path(request.url.path)
        if (
            host_name not in _ALLOWED_HOSTS
            or (origin is not None and (not public or origin not in _CORS_ORIGINS))
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "invalid_local_request",
                        "message": "Request was rejected",
                    }
                },
            )
        if not public:
            supplied = request.headers.get("x-broker-client-secret", "")
            if not hmac.compare_digest(supplied, client_secret):
                error = AuthenticationError("Broker client authentication is required")
                return JSONResponse(
                    status_code=error.status_code,
                    content={"error": {"code": error.code, "message": str(error)}},
                )
        content_length = request.headers.get("content-length")
        if content_length and (
            not content_length.isdigit() or int(content_length) > _MAX_REQUEST_BYTES
        ):
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "request_too_large",
                        "message": "Request body is too large",
                    }
                },
            )
        chunks: list[bytes] = []
        total = 0
        try:
            async with asyncio.timeout(10):
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > _MAX_REQUEST_BYTES:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "request_too_large",
                                    "message": "Request body is too large",
                                }
                            },
                        )
                    chunks.append(chunk)
        except TimeoutError:
            return JSONResponse(
                status_code=408,
                content={
                    "error": {
                        "code": "request_timeout",
                        "message": "Request body timed out",
                    }
                },
            )
        request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(BrokerError)
    async def broker_error_handler(_request: Request, exc: BrokerError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Request body did not match the broker schema",
                }
            },
            headers={"Cache-Control": "no-store"},
        )

    async def health_response() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="docker-broker",
            docker_available=await docker_runner.docker_available(),
            policy_version=settings.policy_version,
            boot_id=lease_store.boot_id,
        )

    @app.get("/health", response_model=HealthResponse)
    async def public_health() -> HealthResponse:
        return await health_response()

    @app.post(
        "/v1/coder/confirmations", response_model=CoderConfirmationResponse
    )
    async def coder_confirmation(
        body: ConfirmationAttempt,
    ) -> CoderConfirmationResponse:
        return await coder_operations.confirm(body)

    @app.get(
        "/v1/coder/status/{operation_digest}",
        response_model=CoderOperationStatus,
    )
    async def coder_status(operation_digest: str) -> CoderOperationStatus:
        return await coder_operations.status(operation_digest)

    @app.get(
        "/v1/coder/results/{operation_digest}",
        response_model=CoderOperationResult,
    )
    async def coder_result(operation_digest: str) -> CoderOperationResult:
        return await coder_operations.result(operation_digest)

    @app.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return await health_response()

    @app.post("/v1/sessions/activate", response_model=ActivateResponse)
    async def activate(body: ActivateRequest) -> ActivateResponse:
        now = time.monotonic()
        async with activation_lock:
            while activation_attempts and activation_attempts[0] <= now - 600:
                activation_attempts.popleft()
            if len(activation_attempts) >= 5:
                raise RateLimitError("Too many recent activation attempts")
            activation_attempts.append(now)
        workspace = await asyncio.to_thread(
            compose_policy.resolve_workspace, body.workspace
        )
        token, lease = await lease_store.activate(
            session_id=body.session_id,
            owner_id=body.owner_id,
            workspace=workspace,
            lease_seconds=body.lease_seconds,
        )
        return ActivateResponse(
            status="active",
            lease_token=token,
            expires_at=lease.expires_at.isoformat(),
            workspace=str(workspace),
            scope_digest=lease.scope_digest,
            policy_version=settings.policy_version,
        )

    @app.post("/v1/sessions/revoke", response_model=RevokeResponse)
    async def revoke(
        authorization: Annotated[str | None, Header()] = None,
    ) -> RevokeResponse:
        revoked = await lease_store.revoke(_bearer_token(authorization))
        return RevokeResponse(status="revoked" if revoked else "not_active")

    @app.post("/v1/compose/inspect", response_model=ComposeInspectResponse)
    async def inspect_compose(body: ComposeInspectRequest) -> ComposeInspectResponse:
        workspace = await asyncio.to_thread(
            compose_policy.resolve_workspace, body.workspace
        )
        target = ComposeTarget(
            project_directory=body.project_directory,
            compose_files=body.compose_files,
        )
        project = await asyncio.to_thread(compose_policy.validate, workspace, target)
        if body.inspection == "service_status":
            services = await docker_runner.service_status(project)
        else:
            await docker_runner.validate_config(project)
            services = project.summaries
        return ComposeInspectResponse(
            valid=True,
            project=project.project_name,
            services=list(services),
            policy_version=settings.policy_version,
        )

    @app.post("/v1/compose/apply", response_model=ComposeApplyResponse)
    async def apply_compose(
        body: ComposeApplyRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ComposeApplyResponse:
        lease = await lease_store.authorize(_bearer_token(authorization))
        target = ComposeTarget(
            project_directory=body.project_directory,
            compose_files=body.compose_files,
        )
        project = await asyncio.to_thread(
            compose_policy.validate, lease.workspace, target
        )
        result = await docker_runner.apply(project, body, lease)
        return ComposeApplyResponse.model_validate(result)

    @app.get("/v1/runtime/langgraph", response_model=RuntimeInspectResponse)
    async def inspect_langgraph() -> RuntimeInspectResponse:
        return await docker_runner.inspect_langgraph()

    app.state.settings = settings
    app.state.audit = audit
    app.state.lease_store = lease_store
    app.state.compose_policy = compose_policy
    app.state.docker_runner = docker_runner
    app.state.coder_operations = coder_operations
    return app
