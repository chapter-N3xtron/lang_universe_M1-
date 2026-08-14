# Deep Agents persistence

Terminology: `workspace_id` is the durable repository-path binding ID used by
existing Store/database/API records; it is not a visual UI workspace ID. A session
may exist without a repository binding. Artifacts remain associated with their
producing thread/session, not with a repository binding. LangGraph runtime,
checkpoints, and Store are persistence infrastructure, not a workspace entity. See
`openspec/TERMINOLOGY.md` for the compatibility rule.

The LangGraph Agent Server checkpoint for each Jasper thread is the source of truth
for that thread's transcript, graph position, tool results, and resumable execution.
Coder runs as a native nested LangGraph subgraph and inherits that checkpoint context,
so pending file and command approvals propagate directly to Agent Chat UI and resume
on the same thread.

Coder does not maintain a second live checkpoint history. LangGraph checkpoints retain
failed-run execution evidence, while the selected Git repository remains authoritative
for actual files and diffs. The application does not scan the filesystem or copy an
inferred patch into Store after a failed command. A later explicitly approved Coder
turn can inspect `git status` and `git diff` when recovery is needed.

The existing LangGraph Store session manifest remains authoritative for linked threads,
workspace relationships, returned session summaries, Research evidence references,
and visual artifacts. The application-owned PostgreSQL `session_catalog` schema is a
rebuildable query projection for the session list and detail UI; it never owns
checkpoint execution state.

Forks import sanitized checkpoint values into a new Agent Server thread. A fork is
blocked while the source has pending work and never inherits pending approval or
unfinished specialist execution. Completed transcript values, artifact and evidence
references, and repository-binding links are inherited through existing Agent Server
and Store APIs. Artifact ownership remains with the producing thread/session.

The former nested Coder checkpoint database is legacy read-only data. Its opaque
SHA-256 session ID remains available only for scoped export compatibility through:

- `GET /api/coding-sessions/export`

`POST /api/coding-sessions/reset` returns `410 Gone`; starting a linked thread or fork
is the supported clean-context path. Legacy data is not replayed into native thread
checkpoints.

Repository `AGENTS.md` is loaded as read-only Deep Agents memory on each agent
construction. Workspace-local `.agents/skills/` is loaded when present. Credential
values remain only in the runtime environment or secret manager.

## macOS host-operation durability

Host operations cross three independently restarting domains without combining their
sources of truth:

- the Agent Server checkpoint owns the exact pending LangGraph interrupt and selected
  repository;
- the UI owns no durable authority and resumes through the ordinary `Command` decision;
- `$HOME/.jasper/macos-host-executor/private/state` owns digest-keyed executor state,
  request process identity, rollback accounting, and the private signing key.

The executor uses a monotonic, single-use lifecycle. Concurrent attempts lock on the
plan digest; duplicate approval, browser retry, or resume returns the same terminal
signed receipt and never repeats a mutation. After restart, a pending/running uncertain
mutation is not replayed silently. It is reported for human inspection or requires a
new request. Cancellation and timeout address only the recorded request-owned process
group; launcher shutdown signals only the exact PID and full command identity.

Terminal receipts are redacted, non-secret persistence evidence. Only the read-only
public verification key is visible to Docker. A verified successful receipt is the sole
source of truth for a Mac effect; failed, partial, cancelled, expired, or unverifiable
receipts preserve known mutations and rollback uncertainty without claiming recovery.
Repository work and checkpoints remain usable when the executor was never installed.
If it is installed but policy, integrity, identity, or health validation fails, core
startup fails closed until the operator repairs or explicitly disables the feature.

The installed runtime is an immutable, integrity-manifested snapshot outside writable
repositories. Ordinary start/restart never updates it or runs a canary. The operator's
private `policy.json` persists across explicit reinstalls and must be reviewed and pinned
separately. Rollback/disable stops the exact executor, removes or moves the installation
out of `$HOME/.jasper/macos-host-executor`, and restarts ordinary Coding; it does not
rewrite checkpoints, receipts, local Git state, or substitute the selected workspace.
