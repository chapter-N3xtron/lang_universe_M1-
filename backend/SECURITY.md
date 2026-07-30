# Coding-agent security boundary

The Deep Agents coding backend defaults to `read_only`. A request must set
`execution_mode` to the exact value `approval` before mutation tools are added
to the agent. Legacy values such as `live` and `async` remain read-only.

## Filesystem policy

- The workspace must be an existing absolute directory and is resolved before
  the agent starts.
- Deep Agents `FilesystemBackend` runs in virtual-root mode.
- Built-in filesystem writes are always denied.
- Reads of `.env` files, `.git`, and private-key formats are denied.
- `AGENTS.md`, `.env`, `.git`, SSH/AWS/GPG paths, and private-key formats cannot
  be changed through the approval tools.
- Approved writes and edits resolve their parent and target after approval,
  reject traversal and symlink escapes, cap content at 1 MB, and use an atomic
  replacement in the target directory.

## Human approval

Approval mode exposes only these mutation tools:

- `approved_write_file`
- `approved_edit_file`
- `run_workspace_command`

Each call produces a standard LangGraph HITL interrupt. Reviewers may approve,
edit, or reject it. Edited arguments are passed through the same policy checks
as the original action. Requests include `expires_at` and default to a 900
second lifetime; an approval received after expiry is converted to a rejection.

## Command policy

Commands are argv arrays, never shell strings. Pipes, redirects, substitutions,
control operators, absolute paths, parent traversal, and symlink escapes are
rejected. The allowlist is limited to read-only Git inspection, ripgrep, pytest,
Ruff checks, Python pytest/compileall, and named npm/pnpm verification scripts.
Processes receive a minimal environment with no inherited credentials, have a
120-second maximum, use bounded output, and redact common credential fields.

This is a constrained local process policy, not operating-system isolation.
Approved tests and package scripts execute repository code with the backend
user's permissions. A container/VM/remote sandbox is still required for
unattended execution or untrusted users. `LocalShellBackend` is intentionally
not used.
