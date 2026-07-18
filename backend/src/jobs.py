"""In-memory async job runner for long-running agent tasks.

Jobs run in background threads so the HTTP request returns immediately.
Clients poll `/api/jobs/{id}` for status and results.
"""

import threading
import time
import uuid
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = Job(id=job_id, status="pending")
    return job_id


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def run_job(job_id: str, fn: Callable[[], str]) -> None:
    def worker():
        with _lock:
            job = _jobs.get(job_id)
            if not job:
                return
            job.status = "running"
            job.updated_at = time.time()
        try:
            result = fn()
            with _lock:
                _jobs[job_id].status = "completed"
                _jobs[job_id].result = result
                _jobs[job_id].updated_at = time.time()
        except Exception as e:
            with _lock:
                _jobs[job_id].status = "failed"
                _jobs[job_id].error = str(e)
                _jobs[job_id].updated_at = time.time()

    threading.Thread(target=worker, daemon=True).start()


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
