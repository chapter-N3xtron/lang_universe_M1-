## Why

The repository needs an explicit architecture and operating contract for Coder as a subagent so implementation work can be delegated without unclear boundaries, excessive approval prompts, or ambiguous reporting back to Jasper. This change records observed current behavior separately from proposed requirements and is planning-only; it does not implement the architecture or workflow.

## What Changes

- Record observed current behavior and unresolved questions about Coder architecture and workflow.
- Define proposed requirements for Coder’s architecture, subagent roles and boundaries, tool access, synchronous/asynchronous operation, approval and authorization, and approval-noise reduction.
- Define routing criteria for smaller models handling routine formatting, lint, and type-check work.
- Define the required post-Coder reporting workflow: after Coder completes, Jasper must summarize Coder’s report in the context of the active conversation rather than dumping the raw report into chat.
- Establish that no runtime, prompt, permission, model-routing, or UI implementation is authorized by this change.

## Capabilities

### New Capabilities

- `coder-architecture-workflow`: Planning contract for Coder architecture, delegation boundaries, tools, execution modes, authorization, model routing, and Jasper’s contextual post-Coder reporting.

### Modified Capabilities

- None.

## Impact

Planning artifacts only under `openspec/changes/coder-architecture-workflow/`. No application code, APIs, dependencies, credentials, permissions, or execution behavior are changed.

## Terminology boundary

Coder’s selected workspace is the repository path/root used for its tools, not a
visual UI workspace. If a durable binding is represented, `workspace_id` retains its
existing wire/storage meaning as a repository binding ID. Sessions may exist without
that binding; LangGraph runtime/Store are infrastructure; and artifacts remain tied
to the producing thread/session. See `openspec/TERMINOLOGY.md`.
