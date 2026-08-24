# Coding-agent security boundary

The selected **repository path/root** is a host identity, not an Agent Server
container path. The Agent Server does not mount selected repositories or broad host
roots. Native Custodian at `127.0.0.1:8765` is the sole Coder repository filesystem
and command boundary.

The Deep Agents coding backend defaults to `read_only`. A request must explicitly set
`execution_mode` to `approval` or `autonomous` before mutation or command tools are
available. Legacy mode values remain read-only.

## Native Custodian backend

Coder and Jasper use the documented Deep Agents `BackendProtocol` through
`CustodianBackend`. Host paths are validated lexically in the Agent Server because they
need not exist there; Custodian canonicalizes and verifies the exact path on the host.
Agent actions never fall back to the browser picker's current repository.

Custodian applies one sensitive-path refusal policy to listing, reads, glob, grep,
revision checks, writes, edits, and recursive deletes. It refuses `.env*`, `.git`,
credential directories/files, and private-key formats. Every text result is redacted.
Writes and edits use checked atomic replacement, and writes, edits, and deletes require
a current revision precondition. Jasper's selected-repository backend is read-only.
The separate host-file preflight canonicalizes/refuses a path without reading content;
the subsequent bounded text read applies the same refusal and redaction policy.

## Commands

There is no `LocalShellBackend`, generic host-worker tool, or arbitrary shell-string
API. Coder receives typed Custodian tools:

- `custodian_command` for a narrow project-executable allowlist;
- `custodian_git` for allowlisted local Git subcommands;
- `custodian_compose_read` and `custodian_compose_change` for bounded Docker Compose
  inspection and deployment changes;
- `custodian_github_publish` to create one private repository in the fixed
  `chapter-N3xtron` account, push the selected committed branch, and replace `origin`.

Custodian uses no shell, a sanitized environment and isolated `HOME`, bounded argv,
time, and output, and process-group termination on timeout. Provider credentials are
not inherited. Sensitive or out-of-repository path arguments are refused. Docker
Compose automatic `.env` loading is disabled. The GitHub publication action runs only
fixed Git and GitHub CLI operations. It uses broker-held macOS authority without
forwarding environment tokens to Coder and refuses dirty tracked changes, detached
branches, another owner, or public visibility.

In approval mode, repository mutations and all command tools produce normal LangGraph
human-in-the-loop interrupts. Autonomous mode retains explicit approval boundaries for
Docker Compose deployment changes and GitHub publication. Read-only mode exposes no
command tools and its backend refuses every mutation.

## Container mounts

The Agent Server Compose service retains only narrow application-data mounts for the
todo file, OCR uploads, and coding checkpoints. It has no `${HOME}`,
`/Volumes/Storage`, selected-repository, Docker socket, SSH agent, keychain, or provider
credential mount.
