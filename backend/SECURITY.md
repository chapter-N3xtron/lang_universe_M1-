# Coding-agent security boundary

The Deep Agents coding backend defaults to `read_only`. A request must set
`execution_mode` to the exact value `approval` before file mutation or shell
execution is available. Legacy values such as `live` and `async` remain read-only.

## Read-only mode

- The selected workspace must be an existing absolute directory.
- `FilesystemBackend` runs in virtual-root mode at that directory.
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
approved or rejected. Existing approval expiry, cancellation, checkpoint recovery,
and result-return behavior remains in the Coding graph.

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
