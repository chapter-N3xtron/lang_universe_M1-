# Coding-agent security boundary

Terminology: the selected **repository path/root** is the filesystem boundary for a
run. The persisted `workspace_id` field, where present, identifies its durable
repository binding and must not be read as a visual UI workspace ID. A session can
be created without a repository binding; visual workspace layout/preferences are a
separate browser-local presentation concern.

The Deep Agents coding backend defaults to `read_only`. A request must set
`execution_mode` to the exact value `approval` before file mutation or shell
execution is available. Legacy values such as `live` and `async` remain read-only.

## Read-only mode

- The selected repository path/root must be an existing absolute directory.
- `FilesystemBackend` runs in virtual-root mode at that repository root.
- Built-in writes are denied.
- Reads of `.env`, `.git`, and private-key formats are denied.
- No shell execution tool is exposed.

## Approval mode

Approval mode uses Deep Agents' documented `LocalShellBackend`, rooted at the
selected workspace. The agent receives the native filesystem tools and `execute`
tool, so it can edit code, delete files, install dependencies, run tests and builds,
and use normal Git commands without a custom executable allowlist.

The following native tools produce standard LangGraph human-in-the-loop interrupts:

- `write_file`
- `edit_file`
- `delete`
- `execute`

Reviewers may approve, edit, or reject writes, edits, and commands. Deletions may be
approved or rejected. Native LangGraph checkpoints preserve pending approvals and
resume them on the same thread without an application-level replay bridge.

Shell commands start in the selected workspace, have a 120-second default timeout,
and return at most 100,000 bytes. The backend inherits the Agent Server environment
so repository tools work normally. Docker Desktop's SSH agent socket is forwarded to
the container for authenticated Git operations without mounting private key files.

## Trust boundary

`LocalShellBackend` is direct local execution, not an isolated sandbox. Deep Agents
documents that `virtual_mode` and filesystem permission rules do not confine shell
commands. Approval mode is therefore intended only for the repository owner in this
controlled local deployment. Every shell command and mutation requires explicit
human approval. Reviewers must reject commands that access unrelated paths, reveal
secrets, edit `.git` files directly, force-push, delete remote history, or otherwise
exceed the selected repository task.
