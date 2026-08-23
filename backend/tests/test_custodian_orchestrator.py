from __future__ import annotations

from custodian_orchestrator import orchestrator_worker_url


def test_native_orchestrator_ignores_container_worker_address():
    assert orchestrator_worker_url(
        {"CUSTODIAN_WORKER_URL": "http://host.docker.internal:8766"}
    ) == "http://127.0.0.1:8765"


def test_native_orchestrator_accepts_dedicated_worker_override():
    assert orchestrator_worker_url(
        {"CUSTODIAN_ORCHESTRATOR_WORKER_URL": "http://127.0.0.1:9000/"}
    ) == "http://127.0.0.1:9000"
