"""Non-secret deployment identity for the Agent Chat persistence boundary."""

from __future__ import annotations

import os

from fastapi import FastAPI


app = FastAPI()


@app.get("/runtime-identity")
def runtime_identity() -> dict[str, object]:
    """Let clients reject runtimes that are not bound to durable persistence."""

    runtime_id = os.getenv("SESSION_RUNTIME_ID", "unverified")
    durable = os.getenv("SESSION_RUNTIME_MODE") == "durable"
    return {
        "runtime_id": runtime_id,
        "durable": durable,
        "persistence": "postgres" if durable else "unverified",
    }
