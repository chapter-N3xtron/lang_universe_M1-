"""Non-secret deployment identity for the Agent Chat persistence boundary."""

from __future__ import annotations

import os

from fastapi import FastAPI

from src.session_catalog_routes import router as session_catalog_router
from src.workspace_policy import host_operation_request_available

app = FastAPI()
app.include_router(session_catalog_router)


@app.get("/runtime-identity")
def runtime_identity() -> dict[str, object]:
    """Let clients reject runtimes that are not bound to durable persistence."""

    runtime_id = os.getenv("SESSION_RUNTIME_ID", "unverified")
    durable = os.getenv("SESSION_RUNTIME_MODE") == "durable"
    return {
        "runtime_id": runtime_id,
        "durable": durable,
        "persistence": "postgres" if durable else "unverified",
        "command_runtime": "linux_agent_server_container",
        "native_host_operations": "unavailable_without_separate_approval",
        "host_operation_request": (
            "available" if host_operation_request_available() else "unavailable"
        ),
    }
