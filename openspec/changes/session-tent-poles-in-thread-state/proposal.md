## Why

Human-approved session tent poles currently live as strings in the owner-scoped session Store record and in the application-owned `session_catalog.tent_poles` projection table, while `backend/src/chat_ui.py` has no tent-pole channel in its LangGraph `State`. That makes a custom catalog table part of the effective read/write authority and leaves same-thread graph workflows without an authoritative structured value in their checkpointed thread state.

LangGraph documents checkpointed graph state as thread-scoped memory and Store as application-defined long-term data that can span threads. Tent poles approved for one session belong in the former. Deliberately promoting one to installation-wide memory belongs in the latter and requires a separate human decision.

## What Changes

- Define `tent_poles` as an authoritative LangGraph thread-state list for one thread after that state key has been established.
- Define each approved tent pole as a structured value with exactly the proposed contract fields `id`, `content`, `priority`, and `approved_at`, retaining the existing maximum of 20.
- Permit workflows and tools executing in that same authoritative thread to read the list, while prohibiting cross-thread lookup or access.
- Require separate explicit human approval before any tent pole is promoted to installation-wide LangGraph Store memory; ordinary thread-state approval or update does not authorize a Store write.
- Preserve every legacy Store and `session_catalog.tent_poles` record and use them only as compatibility fallback while the thread-state key is absent, until migration readback and rollback are verified.
- Make a present, explicitly empty thread-state list authoritative, so it does not fall back to legacy values.
- Plan a reversible, dry-run-first migration with deterministic conversion, readback comparison, rollout gates, and rollback to legacy reads without destructive cleanup.
- Add planning artifacts only. This change does not implement, deploy, migrate, delete tables or records, add document linking, or change general UI behavior.

## Capabilities

### New Capabilities

- `session-tent-poles`: Human-approved session tent poles as structured, thread-scoped LangGraph state with isolated reads, separately approved Store promotion, and reversible legacy compatibility.

### Modified Capabilities

- None. This change uses `anatomy-of-a-session` as conceptual context without altering that change.

## Impact

A future implementation would affect the `chat_ui` state contract, authenticated tent-pole approval/update handling, same-thread workflow/tool inputs, session-detail and close compatibility adapters, and migration/readback tooling. Existing `session_catalog.tent_poles` rows and existing Store session records remain intact. No implementation, database, deployment, existing OpenSpec change, unrelated file, document-linking behavior, or general UI behavior is authorized here.

Governance reference: `GOVERNANCE_FRAMEWORK.md`.
