# Workspace terminology

This repository uses two deliberately different meanings for workspace-related language:

- **Repository binding**: the durable association between a session/thread and a
  repository path. The existing technical field `workspace_id` is the opaque ID for
  this binding. It is not a visual UI workspace ID. Existing database columns, Store
  namespaces/keys, API fields, and legacy persisted records retain this name for
  compatibility.
- **Repository path/root**: the selected filesystem directory associated with a
  repository binding. New explanatory prose and internal names should prefer
  `repository_root`, `repository_path`, or `repository_binding_id` where that does
  not alter an existing contract. An absent path means the session has no repository
  binding; sessions do not require one.
- **Visual workspace**: the Chat, Split, and Visual presentation/layout surface and
  its browser-local preferences. Visual workspace preference keys and behavior are
  separate from repository binding identity.

Artifacts are currently associated with the producing thread/session, not with a
repository binding. Do not infer repository ownership from an artifact reference.
LangGraph runtime, checkpoints, and Store are infrastructure for execution and
persistence; they are not a workspace entity.

This is a terminology and documentation rule, not a migration. Renaming the
`workspace_id` wire/storage field or changing session/artifact ownership requires a
separate compatibility-reviewed change.
