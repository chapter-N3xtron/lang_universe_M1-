"""Non-agent orchestration: pending check, confirmation, single use, execution, receipt."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from .adapters import ActionAdapter, AdapterResult
from .confirmation import ConfirmationProvider, PendingInterruptChecker
from .errors import ExecutorError, StateConflictError
from .models import (
    ApplicationInstallAction,
    ConfirmationAttempt,
    DockerSandboxAction,
    DownloadAction,
    HostOperationRequest,
    InputHash,
    LifecycleState,
    NativeApplicationAction,
    ProcessSummary,
    Receipt,
    RollbackReport,
    SignedReceipt,
)
from .policy import ActionPolicy, ExecutionPlan
from .security import redact
from .signing import ReceiptSigner
from .state import StateStore


class ExecutorCore:
    def __init__(
        self,
        *,
        policy: ActionPolicy,
        store: StateStore,
        signer: ReceiptSigner,
        pending: PendingInterruptChecker,
        confirmation: ConfirmationProvider,
        adapters: Mapping[str, ActionAdapter],
    ):
        self.policy = policy
        self.store = store
        self.signer = signer
        self.pending = pending
        self.confirmation = confirmation
        self.adapters = dict(adapters)
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self.store.recover_after_restart()
        for interrupted in self.store.unreceipted_uncertain():
            receipt = Receipt(
                request_digest=interrupted.digest,
                request_id=interrupted.request_id,
                terminal_status=LifecycleState.UNCERTAIN,
                finished_at=datetime.now(UTC),
                action_category=interrupted.plan.action.category,
                executable="unavailable-after-restart",
                argv_summary=(),
                process=ProcessSummary(),
                verified_outcome=False,
                rollback=RollbackReport(
                    attempted=False,
                    succeeded=None,
                    detail="not replayed; inspect host state before a new request",
                ),
                remaining_human_step="Inspect declared host mutations before requesting any retry.",
                message="Executor restarted after confirmation or execution; mutation state is uncertain.",
            )
            self.store.attach_recovery_receipt(
                interrupted.digest, self.signer.sign(receipt)
            )

    def start(
        self, attempt: ConfirmationAttempt
    ) -> tuple[LifecycleState, SignedReceipt | None]:
        request = HostOperationRequest.from_attempt(attempt)
        request.assert_unexpired()
        plan = self.policy.plan(request.plan)
        if not self.pending.is_pending(
            request.thread_id, request.interrupt_id, request.digest
        ):
            raise StateConflictError("matching LangGraph interrupt is not pending")
        state, receipt = self.store.create(request)
        if receipt or state.terminal:
            return state, receipt
        if state != LifecycleState.REQUESTED:
            raise StateConflictError("request is already in progress")
        self.store.claim_confirmation(request.digest)
        cancel = threading.Event()
        with self._lock:
            self._cancel[request.digest] = cancel
        worker = threading.Thread(
            target=self._execute,
            args=(request, plan, cancel),
            name=f"host-operation-{request.digest[:12]}",
            daemon=True,
        )
        worker.start()
        return state, None

    def _execute(
        self,
        request: HostOperationRequest,
        plan: ExecutionPlan,
        cancel: threading.Event,
    ) -> None:
        started: datetime | None = None
        try:
            if cancel.is_set():
                self._terminal(
                    request,
                    plan,
                    LifecycleState.CANCELLED,
                    message="cancelled before confirmation",
                )
                return
            if not self.confirmation.confirm(request, plan):
                self._terminal(
                    request,
                    plan,
                    LifecycleState.REJECTED,
                    message="native confirmation rejected or invalid",
                )
                return
            request.assert_unexpired()
            if not self.pending.is_pending(
                request.thread_id, request.interrupt_id, request.digest
            ):
                self._terminal(
                    request,
                    plan,
                    LifecycleState.REJECTED,
                    message="LangGraph interrupt no longer pending",
                )
                return
            self.policy.revalidate(request.plan)
            self.store.transition(request.digest, LifecycleState.CONFIRMED)
            if cancel.is_set():
                self._terminal(
                    request,
                    plan,
                    LifecycleState.CANCELLED,
                    message="cancelled before execution",
                )
                return
            self.store.transition(request.digest, LifecycleState.RUNNING)
            started = datetime.now(UTC)
            adapter = self.adapters.get(request.plan.action.category)
            if not adapter:
                raise ExecutorError("no trusted adapter configured for category")
            result = adapter.execute(
                request.plan.action,
                plan,
                timeout=request.plan.timeout_seconds,
                output_limit=request.plan.output_limit_bytes,
                cancel=cancel,
            )
            status = self._status(result)
            self._terminal(request, plan, status, started=started, result=result)
        except ValueError as exc:
            status = (
                LifecycleState.EXPIRED
                if "expired" in str(exc)
                else LifecycleState.FAILED
            )
            self._terminal_if_possible(request, plan, status, started, str(exc))
        except Exception as exc:  # fail closed and persist a redacted terminal fact
            self._terminal_if_possible(
                request,
                plan,
                LifecycleState.UNCERTAIN if started else LifecycleState.FAILED,
                started,
                str(exc),
            )
        finally:
            with self._lock:
                self._cancel.pop(request.digest, None)

    @staticmethod
    def _status(result: AdapterResult) -> LifecycleState:
        if result.process.cancelled:
            return (
                LifecycleState.PARTIAL if result.partial else LifecycleState.CANCELLED
            )
        if result.process.timed_out:
            return LifecycleState.PARTIAL if result.partial else LifecycleState.FAILED
        if result.success and result.verified:
            return LifecycleState.SUCCEEDED
        return LifecycleState.PARTIAL if result.partial else LifecycleState.FAILED

    def _terminal_if_possible(
        self,
        request: HostOperationRequest,
        plan: ExecutionPlan,
        status: LifecycleState,
        started: datetime | None,
        message: str,
    ) -> None:
        current = self.store.get(request.digest)
        if not current or current[0].terminal:
            return
        # Pre-execution failure states have narrower legal terminal transitions.
        if current[0] == LifecycleState.REQUESTED:
            self.store.transition(request.digest, LifecycleState.CONFIRMING)
        if current[0] in {
            LifecycleState.REQUESTED,
            LifecycleState.CONFIRMING,
        } and status not in {
            LifecycleState.REJECTED,
            LifecycleState.EXPIRED,
            LifecycleState.CANCELLED,
        }:
            status = LifecycleState.REJECTED
        self._terminal(request, plan, status, started=started, message=message)

    def _terminal(
        self,
        request: HostOperationRequest,
        plan: ExecutionPlan,
        status: LifecycleState,
        *,
        started: datetime | None = None,
        result: AdapterResult | None = None,
        message: str = "",
    ) -> SignedReceipt:
        result = result or AdapterResult(False, False)
        receipt = Receipt(
            request_digest=request.digest,
            request_id=request.request_id,
            terminal_status=status,
            started_at=started,
            finished_at=datetime.now(UTC),
            action_category=request.plan.action.category,
            executable=plan.executable,
            argv_summary=tuple(redact(value, limit=1024) for value in plan.argv),
            working_directory=plan.working_directory,
            approved_paths=plan.approved_paths,
            observed_paths=result.observed_paths,
            artifact_hashes=self._artifact_hashes(request),
            process=result.process,
            verified_outcome=result.verified and status == LifecycleState.SUCCEEDED,
            observed_mutations=result.mutations,
            rollback=result.rollback,
            remaining_human_step=result.remaining_human_step,
            message=redact(result.message or message, limit=4096),
        )
        signed = self.signer.sign(receipt)
        self.store.finish(request.digest, signed)
        return signed

    @staticmethod
    def _artifact_hashes(request: HostOperationRequest) -> tuple[InputHash, ...]:
        action = request.plan.action
        if isinstance(action, DownloadAction):
            return (InputHash(path=action.destination, sha256=action.sha256),)
        if isinstance(action, ApplicationInstallAction):
            return (
                InputHash(path=action.artifact_path, sha256=action.artifact_sha256),
            )
        if isinstance(action, DockerSandboxAction):
            compose_path = (
                Path(action.workspace) / action.project_directory / action.compose_file
            )
            return (InputHash(path=str(compose_path), sha256=action.compose_sha256),)
        if isinstance(action, NativeApplicationAction):
            values = list(action.configuration)
            if action.script:
                values.insert(0, action.script)
            return tuple(values)
        return ()

    def cancel(self, digest: str) -> LifecycleState:
        with self._lock:
            event = self._cancel.get(digest)
        current = self.store.get(digest)
        if not current:
            raise StateConflictError("unknown request")
        if current[0].terminal:
            return current[0]
        if event:
            event.set()
            return current[0]
        raise StateConflictError("request is not owned by this executor process")

    def status(self, digest: str) -> tuple[LifecycleState, SignedReceipt | None] | None:
        return self.store.get(digest)
