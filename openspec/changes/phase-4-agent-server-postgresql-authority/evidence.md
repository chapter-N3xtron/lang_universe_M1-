# Phase 4 focused cutover evidence

## Source and contract verification

- The Phase 4 and directly affected test set passed: **96 passed, 26 warnings**.
- The full backend suite completed with **335 passed, 4 unrelated failures, 37 warnings**. The remaining failures are outside Phase 4: a removed `chat_ui.call_jasper` test patch target, an OCR route-name expectation, a Research-agent `MagicMock` compatibility issue, and a legacy LangSmith evaluation that requires tracing.
- Ruff passed for every Phase 4 source and test file. Repository-wide Ruff still reports unrelated existing findings in EPUB, session-catalog, speech-to-text, and Custodian test files.
- Graph-construction tests confirm top-level Jasper, standalone Coder, and the Jasper-nested Coder bridge have no application-owned checkpointer or Store.
- Temporal replay, retry, attachment, heartbeat, and cancellation tests confirm Temporal owns only outer orchestration. A retried activity joins an existing Agent Server run by operation correlation when available and does not start duplicate inner work.
- Production Coder and Temporal paths contain no import or call to the legacy Coder persistence manager. Legacy implementation and persisted assets remain present for Phase 9.

## Deployed cutover checks

Deployment boundary: Docker Compose in this runtime worktree, with the human-facing frontend on port 3002 and Agent Server on port 8123.

- Deployed image `jasper-langgraph:current`: `sha256:8366ea8bd0e8aca4e4bce741718c4aec61b8302f68177b90f2453effa0cb385e`.
- Deployed image `jasper-runtime-sidecar:latest`: `sha256:778fe4f060cd42a8610f6794db99a3136de1f009a7d70fd0b15534d70b4d945f`.
- Agent Server reports both registered graphs: `chat_ui` and `coder`.
- Jasper checkpoint probe `1f1a28f6-54b3-6879-8000-f6e9e10a6031` recovered unchanged after Agent Server restart.
- Standalone Coder checkpoint probe `1f1a28de-b40b-64c8-8000-635a2ad075c8` recovered unchanged after PostgreSQL restart, Agent Server restart, and final image recreation.
- With Redis stopped, Agent Server still read the committed Coder checkpoint successfully. Redis was restarted without flushing or deleting data.
- With PostgreSQL stopped, a checkpoint mutation timed out and returned no success response. PostgreSQL was restarted and the service recovered.
- A second run submitted to an occupied Coder thread with Agent Server's `reject` concurrency strategy returned HTTP 409. Two runs submitted on distinct threads were both accepted independently and then cancelled before execution.
- A deployed Coder run with conflicting declared and runtime thread identities returned a structured `RuntimeIdentityError` without echoing either identity in the error message.
- A missing authoritative thread returned HTTP 404, and a malformed authoritative state update returned HTTP 422. Neither condition consulted or imported legacy state.
- A disposable Store item containing a forged checkpoint marker was accepted and then deleted; the Coder checkpoint ID remained unchanged, confirming Store cannot reconstruct or advance checkpoint state.
- All five deployed services were healthy after the checks: PostgreSQL, Redis, Agent Server, sidecar, and frontend.

These are focused Phase 4 checks, not broad product or browser acceptance.

## Rollback boundary

Rollback must preserve the Agent Server PostgreSQL volume and must not reactivate the legacy Coder persistence manager, legacy export/reset endpoints, or direct Coder execution inside Temporal. A compatible prior image may be restored only if it continues to use Agent Server PostgreSQL as the sole checkpoint authority and understands the current graph state. If no such image is available, the safe response is a forward fix; falling back to legacy state would create split authority and is not an acceptable rollback.
