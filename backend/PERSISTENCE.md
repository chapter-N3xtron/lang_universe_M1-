# Deep Agents persistence

The LangGraph server remains the source of truth for UI conversation history.
The coding agent receives that history on its first turn, then persists its own
tool, subagent, summary, and pending-approval state in a nested LangGraph
checkpointer.

Sessions use an opaque SHA-256 identifier derived from:

- authenticated user identity (or `anonymous` for the local single-user UI),
- LangGraph UI thread ID, and
- the resolved repository root.

This prevents one UI thread from reusing coding state in another repository or
another user's session. Raw repository and user values are not embedded in the
checkpoint thread ID.

The default database is `data/deep_agents_checkpoints.sqlite3`, which survives
backend and LangGraph restarts without requiring Docker. Set
`CODING_CHECKPOINT_DB_URI` to use the installed async Postgres checkpointer in a
deployment that exposes a dedicated connection URI. Credential values belong
only in the runtime environment or secret manager.

Repository `AGENTS.md` is loaded as read-only Deep Agents memory on each agent
construction. Workspace-local `.agents/skills/` is loaded when present. Both
remain repository-scoped; the mutation policy prevents the coding agent from
rewriting `AGENTS.md`.

The local sidecar exposes scoped lifecycle operations:

- `GET /api/coding-sessions/export`
- `POST /api/coding-sessions/reset`

Both require the thread, workspace, and user scope used to derive the session.
Reset deletes only that opaque checkpoint thread. Export returns the latest
checkpoint's messages and metadata; it does not expose database credentials or
other session IDs.
