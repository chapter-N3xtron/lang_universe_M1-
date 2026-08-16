from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from docker_broker.config import Settings
from docker_broker.errors import ApprovalRejected, BrokerError, LeaseError, PolicyError
from docker_broker.langgraph import PendingInterruptChecker
from docker_broker.leases import Lease, LeaseStore
from docker_broker.models import (
    CoderConfirmationResponse,
    CoderOperationResult,
    CoderOperationStatus,
    ComposeApplyRequest,
    ComposeApplyResponse,
    ComposeTarget,
    ConfirmationAttempt,
    OperationLifecycle,
    TerminalOperationState,
)
from docker_broker.policy import ComposePolicy
from docker_broker.runner import DockerRunner


@dataclass
class _Operation:
    digest: str
    plan_digest: str
    state: OperationLifecycle = "requested"
    result: dict[str, object] | None = None


class CoderOperationManager:
    def __init__(
        self,
        settings: Settings,
        checker: PendingInterruptChecker,
        leases: LeaseStore,
        policy: ComposePolicy,
        runner: DockerRunner,
    ) -> None:
        self._settings = settings
        self._checker = checker
        self._leases = leases
        self._policy = policy
        self._runner = runner
        self._operations: dict[str, _Operation] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._scope_locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def confirm(self, attempt: ConfirmationAttempt) -> CoderConfirmationResponse:
        workspace_value = await asyncio.to_thread(
            self._checker.pending_workspace, attempt
        )
        if workspace_value is None:
            raise LeaseError("Pending Docker confirmation was not verified")
        workspace = await asyncio.to_thread(
            self._policy.resolve_workspace, workspace_value
        )
        digest = self.operation_digest(workspace, attempt)
        async with self._lock:
            operation = self._operations.get(digest)
            if operation is None:
                operation = _Operation(
                    digest=digest,
                    plan_digest=attempt.plan.digest,
                )
                self._operations[digest] = operation
                task = asyncio.create_task(self._execute(operation, attempt, workspace))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        return CoderConfirmationResponse(**self._status_values(operation))

    @staticmethod
    def operation_digest(workspace: Path, attempt: ConfirmationAttempt) -> str:
        material = json.dumps(
            {
                "workspace": str(workspace),
                "plan": attempt.plan.model_dump(mode="json"),
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _status_values(operation: _Operation) -> dict[str, object]:
        return {
            "operation_digest": operation.digest,
            "plan_digest": operation.plan_digest,
            "state": operation.state,
            "result_available": operation.result is not None,
        }

    async def status(self, digest: str) -> CoderOperationStatus:
        operation = await self._get(digest)
        return CoderOperationStatus(**self._status_values(operation))

    async def result(self, digest: str) -> CoderOperationResult:
        operation = await self._get(digest)
        if operation.result is None or operation.state not in {
            "succeeded",
            "failed",
            "rejected",
        }:
            raise PolicyError("Operation result is unavailable")
        state: TerminalOperationState = operation.state
        return CoderOperationResult(
            operation_digest=operation.digest,
            plan_digest=operation.plan_digest,
            state=state,
            result=operation.result,
        )

    async def _get(self, digest: str) -> _Operation:
        if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
            raise PolicyError("Operation digest is invalid")
        async with self._lock:
            operation = self._operations.get(digest)
        if operation is None:
            raise PolicyError("Operation is unavailable")
        return operation

    async def _execute(
        self, operation: _Operation, attempt: ConfirmationAttempt, workspace: Path
    ) -> None:
        operation.state = "confirming"
        scope = LeaseStore._scope_digest(
            attempt.thread_id, self._settings.owner_id, workspace
        )
        async with self._lock:
            scope_lock = self._scope_locks.setdefault(scope, asyncio.Lock())
        try:
            async with scope_lock:
                lease = await self._leases._active_for_scope(
                    session_id=attempt.thread_id,
                    owner_id=self._settings.owner_id,
                    workspace=workspace,
                )
                if lease is None:
                    _token, lease = await self._leases.activate(
                        session_id=attempt.thread_id,
                        owner_id=self._settings.owner_id,
                        workspace=workspace,
                        lease_seconds=self._settings.lease_seconds,
                    )
            operation.state = "running"
            response = await self._apply(attempt, workspace, lease)
        except ApprovalRejected:
            operation.state = "rejected"
            operation.result = self._generic_result(attempt, "Operation was rejected")
        except (BrokerError, OSError, RuntimeError, ValueError):
            operation.state = "failed"
            operation.result = self._generic_result(attempt, "Operation failed")
        else:
            operation.state = "succeeded"
            operation.result = {
                "request_id": response.request_id,
                "operation": response.operation,
                "project": response.project[:256],
                "services": [service[:256] for service in response.services[:40]],
                "message": "Operation succeeded",
            }

    @staticmethod
    def _generic_result(
        attempt: ConfirmationAttempt, message: str
    ) -> dict[str, object]:
        return {
            "request_id": attempt.plan.request_id,
            "operation": attempt.plan.operation,
            "message": message,
        }

    async def _apply(
        self, attempt: ConfirmationAttempt, workspace: Path, lease: Lease
    ) -> ComposeApplyResponse:
        if attempt.plan.operation == "build" and not self._settings.allow_builds:
            raise PolicyError("builds are disabled on this broker")
        target = ComposeTarget(
            project_directory=attempt.plan.project_directory,
            compose_files=attempt.plan.compose_files,
        )
        project = await asyncio.to_thread(self._policy.validate, workspace, target)
        request = ComposeApplyRequest.model_validate(
            attempt.plan.model_dump(mode="json")
        )
        response = ComposeApplyResponse.model_validate(
            await self._runner.apply(project, request, lease)
        )
        if (
            response.request_id != attempt.plan.request_id
            or response.operation != attempt.plan.operation
        ):
            raise PolicyError("Docker operation result did not match the request")
        return response

    async def close(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
