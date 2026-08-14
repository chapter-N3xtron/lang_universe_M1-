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
and return at most 100,000 bytes. Authorized repository roots under the host home
folder and `/Volumes/Storage` retain their absolute paths inside the container. The
host `.ssh`, `.aws`, `.gnupg`, and GitHub CLI configuration directories are masked.
No GitHub token or SSH agent socket is supplied to the shared Agent Server container,
so local Git remains available but authenticated repository creation and remote push
are unavailable.

## Trust boundary

`LocalShellBackend` is direct local execution, not an isolated sandbox. Deep Agents
documents that `virtual_mode` and filesystem permission rules do not confine shell
commands. Approval mode is therefore intended only for the repository owner in this
controlled local deployment. Every shell command and mutation requires explicit
human approval. Reviewers must reject commands that access unrelated paths, reveal
secrets, edit `.git` files directly, force-push, delete remote history, or otherwise
exceed the selected repository task.

## Hybrid macOS host-operation boundary

The deployment has three security and restart domains:

1. **Agent Server/Coding (Docker):** autonomous repository work and Linux commands.
   A Mac path visible through a bind mount identifies filesystem origin, not command
   runtime. The server-produced execution manifest is authoritative: selected files
   are Mac-host files, commands are Linux-container commands, and native host actions
   are available only when the separate executor is installed and healthy.
2. **Agent Chat UI:** displays the immutable LangGraph interrupt and coordinates an
   attempt. It holds neither execution authority nor signing material. Browser approval
   alone never proves host user presence.
3. **macOS host executor:** a non-agent process at numeric loopback `127.0.0.1:8765`.
   It validates the pending interrupt against Agent Server at `127.0.0.1:8123`, applies
   a pinned local policy, obtains native confirmation, executes one typed action, and
   signs a redacted terminal receipt.

Docker receives only `MACOS_HOST_EXECUTOR_URL` for receipt retrieval and the read-only
public verification directory at `/run/macos-host-executor`. The broad home mount is
shadowed at `.jasper`, `Library/Keychains`, `.ssh`, `.aws`, `.gnupg`, `.config/gh`,
`.docker`, `.kube`, `.azure`, and `.config/gcloud`. No executor private state, staging,
control secret or socket, signing key, Keychain, private key, SSH agent, GitHub
credential, Docker socket, or general sidecar authority crosses into the container.
The public key verifies facts but cannot authorize or forge an operation.

The executor has a finite category policy and no shell endpoint. It rejects arbitrary
shells/interpreters and caller environment, persistence/login items/launch agents,
automatic privilege escalation, credential helpers, GitHub publication or remote Git
push, SSH, and Docker control. GitHub publishing is a separate proposed security domain;
macOS host-operation approval never grants or overlaps GitHub authority.

Every action needs both the exact LangGraph approval and contemporaneous native macOS
confirmation of the digest and policy-derived plan. Passwords, Touch ID, administrator
prompts, Gatekeeper choices, license acceptance, and other GUI authorization remain
manual. A receipt may report a remaining human step; approval, download, process exit,
or staging alone is never evidence of installation.
