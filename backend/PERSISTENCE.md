# Deep Agents persistence

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
references, and workspace links are inherited through existing Agent Server and Store
APIs.

The former nested Coder checkpoint database is legacy read-only data. Its opaque
SHA-256 session ID remains available only for scoped export compatibility through:

- `GET /api/coding-sessions/export`

`POST /api/coding-sessions/reset` returns `410 Gone`; starting a linked thread or fork
is the supported clean-context path. Legacy data is not replayed into native thread
checkpoints.

Repository `AGENTS.md` is loaded as read-only Deep Agents memory on each agent
construction. Workspace-local `.agents/skills/` is loaded when present. Credential
values remain only in the runtime environment or secret manager.
