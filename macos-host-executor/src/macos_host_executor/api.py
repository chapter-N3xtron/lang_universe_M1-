"""Bounded loopback-only FastAPI surface. There is no command endpoint."""

from __future__ import annotations

import ipaddress
import threading
import time
from collections import deque
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from .core import ExecutorCore
from .errors import ExecutorError
from .models import ConfirmationAttempt, LifecycleState, SignedReceipt

DigestPath = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_digest: str
    state: LifecycleState
    receipt_available: bool


class _RateLimiter:
    def __init__(self, attempts: int = 5, window_seconds: int = 60):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._events and self._events[0] <= now - self.window_seconds:
                self._events.popleft()
            if len(self._events) >= self.attempts:
                return False
            self._events.append(now)
            return True


def create_app(
    core: ExecutorCore,
    *,
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "http://127.0.0.1:3002",
        "http://localhost:3002",
    ),
) -> FastAPI:
    app = FastAPI(
        title="macOS Host Executor",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    limiter = _RateLimiter()

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):  # type: ignore[no-untyped-def]
        host = request.client.host if request.client else ""
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=403, detail="loopback clients only"
            ) from None
        if int(request.headers.get("content-length", "0") or 0) > 256 * 1024:
            raise HTTPException(status_code=413, detail="request too large")
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"ok": True, "service": "macos-host-executor", "agent": False}

    @app.post(
        "/v1/confirmations",
        response_model=StatusResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def confirm(http_request: Request) -> StatusResponse:
        if not limiter.allow():
            raise HTTPException(
                status_code=429, detail="confirmation rate limit exceeded"
            )
        body = await http_request.body()
        if len(body) > 256 * 1024:
            raise HTTPException(status_code=413, detail="request too large")
        try:
            # JSON mode preserves strict scalar checking while correctly decoding
            # JSON arrays and RFC-3339 timestamps into their declared wire types.
            attempt = ConfirmationAttempt.model_validate_json(body)
            state_value, receipt = core.start(attempt)
        except (ExecutorError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return StatusResponse(
            plan_digest=attempt.plan.digest,
            state=state_value,
            receipt_available=receipt is not None,
        )

    @app.get("/v1/status/{digest}", response_model=StatusResponse)
    def operation_status(digest: DigestPath) -> StatusResponse:
        value = core.status(digest)
        if not value:
            raise HTTPException(status_code=404, detail="unknown request")
        state_value, receipt = value
        return StatusResponse(
            plan_digest=digest, state=state_value, receipt_available=receipt is not None
        )

    @app.get("/v1/receipts/{digest}", response_model=SignedReceipt)
    def receipt(digest: DigestPath) -> SignedReceipt:
        value = core.status(digest)
        if not value or not value[1]:
            raise HTTPException(status_code=404, detail="terminal receipt unavailable")
        return value[1]

    @app.post("/v1/cancel/{digest}", response_model=StatusResponse)
    def cancel(digest: DigestPath) -> StatusResponse:
        try:
            state_value = core.cancel(digest)
        except ExecutorError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return StatusResponse(
            plan_digest=digest, state=state_value, receipt_available=False
        )

    return app


def require_loopback_bind(host: str) -> None:
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError:
        raise ValueError("executor must bind to a numeric loopback address") from None
