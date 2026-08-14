# macOS Host Executor

A separately installable, non-agent macOS service for the finite action catalog in
`approved-macos-host-operations`. It has no shell-command endpoint and accepts no
caller-supplied executable, argv, environment, request ID, or timestamp.

## Approval and digest contract

The model-facing immutable authority is `HostOperationPlan`. Its only fields are:

- `action`
- `expected_mutations`
- `privilege`
- `timeout_seconds`
- `output_limit_bytes`
- `rollback`
- bounded `expiry_seconds` (1–3600)

The deterministic SHA-256 digest is computed over canonical JSON for that plan only.
The UI sends a strict `ConfirmationAttempt` containing the actual LangGraph
`thread_id`, actual `interrupt_id`, and the plan:

```json
{
  "thread_id": "actual-thread-id",
  "interrupt_id": "actual-interrupt-id",
  "plan": {
    "action": {"category": "host_inspection", "query": "architecture"},
    "expected_mutations": [],
    "privilege": "user",
    "timeout_seconds": 10,
    "output_limit_bytes": 4096,
    "rollback": {
      "strategy": "none",
      "removes_only_request_created_paths": true,
      "may_require_human_inspection": false
    },
    "expiry_seconds": 300
  }
}
```

`POST /v1/confirmations` rejects every extra field. The executor creates the
`HostOperationRequest` itself, wrapping the plan with a random `request_id`, the two
UI-envelope correlation IDs, and server timestamps `created_at` and `expires_at`.
Before confirmation and again before execution it requires
`pending(thread_id, interrupt_id, plan.digest)`. Status responses expose
`plan_digest`; signed receipts keep `request_digest == plan.digest`, allowing the
resumed tool to recompute and verify the authority that was approved.

The native helper displays the complete plan, correlation IDs, server envelope, and
the policy-derived executable/argv/path plan. Policy-derived command fields are never
accepted from the client.

## Security boundary

Security defaults are unusable until all production configuration is explicitly
provided. Exact roots, domains, package names, application identities, and executable
paths come only from trusted local JSON policy. State, staging, the Ed25519 private
key, and confirmation helper remain host-only. The signing API can export only the raw
32-byte public verification key; the CLI writes it separately from private state.

The HTTP API binds only to numeric loopback (`127.0.0.1` or `::1`). It has bounded
confirmation, status, receipt, cancellation, and health routes, permits one active
prompt/execution, and has no general command endpoint. Missing or invalid required
production configuration fails closed with a `deny-all` startup error.

## Production configuration

All authority-bearing inputs are explicit CLI options:

```bash
macos-host-executor \
  --host 127.0.0.1 \
  --port 8765 \
  --policy-json /absolute/host/policy.json \
  --agent-server-url http://127.0.0.1:2024 \
  --confirmation-helper /absolute/host/macos-host-confirmation \
  --state-directory '/absolute/host/private executor state' \
  --public-key-output /absolute/host/receipt-signing.pub
```

The Agent Server URL must be an exact numeric loopback HTTP base URL. For each check,
the executor performs only `GET /threads/{urlencoded thread_id}/state`, with a fixed
response-size limit and network timeout. It accepts no bearer token or callback URL,
does not write Agent Server state, and grants no authority to a general sidecar. The
returned checkpoint must name the exact thread; one pending task interrupt must match
the exact interrupt ID; and that interrupt must contain exactly one
`request_macos_host_operation` action whose args strictly validate as a
`HostOperationPlan` and recompute to the requested digest. Any malformed, unavailable,
oversized, or mismatched state fails closed.

Policy JSON is parsed with unknown fields forbidden; `{}` is a valid explicit deny-all
policy. Application installation also requires the request's exact Team ID to match the
trusted `allowed_application_team_ids[application_id]` policy entry; request data cannot
supply or widen that trust. Native scripts are denied unless their exact SHA-256 digest is
separately operator-pinned in `allowed_native_script_hashes`; Blender starts with factory
settings and automatic embedded-script execution disabled. Child processes receive an
isolated `HOME` and no inherited credential variables. The state directory is forced to
mode `0700`, the private signing key and SQLite state remain private, and the public key
output contains no signing material.

The Python adapters contain the fixed native mechanics. Tests inject fake adapters
and never perform downloads, package operations, mounts, application copies, or
native application launches.

## Operator runbook

### Trust and runtime identity

Treat the deployment as three domains: (1) Docker Agent Server/Coding performs Linux
commands against the exact selected Mac-host bind mount, (2) the browser UI presents
and resumes the standard LangGraph interrupt but has no host authority, and (3) this
native, non-agent executor alone performs policy-approved macOS actions. Agent Server
is `http://127.0.0.1:8123`; executor health is loopback-only at
`http://127.0.0.1:8765/health`. A container test is never a macOS test. Only a verified
successful signed receipt supports a claim about the physical Mac.

### Install and pin policy

From the reviewed repository, an operator at an interactive terminal runs:

```bash
./start_image_pipeline.sh install-host-executor
```

This is the only installation/update path. It asks for literal `INSTALL`, snapshots
source into `$HOME/.jasper/macos-host-executor/runtime`, builds an isolated venv and
compiled Swift confirmation helper, writes an integrity manifest, and makes the runtime
non-writable. It does not start the executor or perform an inspection, mutation, or
canary. Ordinary `start`, `restart`, and `restart-core` never copy from the writable
repository and never update the snapshot.

Review and pin
`$HOME/.jasper/macos-host-executor/private/config/policy.json` before start. It is a
strict explicit allowlist; unknown fields fail closed. `policy.example.json` limits
roots and download domains, allows only the Homebrew cask `blender`, pins Blender's
application executable, and intentionally leaves `allowed_application_team_ids` and
`allowed_native_script_hashes` empty. Consequently typed application copy/install and
agent-authored native scripts remain denied until an operator separately verifies and
pins the required identity or digest. Do not broaden roots to the home folder, Keychains,
credential directories, Docker, or SSH locations.

### Start, status, stop, and failure behavior

```bash
./start_image_pipeline.sh start
./start_image_pipeline.sh status
./start_image_pipeline.sh restart-core
./start_image_pipeline.sh stop
```

If no snapshot exists, host operations are reported unavailable and ordinary Coding
continues. If a snapshot exists, integrity, explicit policy, exact PID/full-command
identity, and health are mandatory; unhealthy executor startup tears Agent Server back
down before the sidecar/UI start. Restart-core stops and starts the executor with the
core. Stop and timeout/cancellation never use name- or port-wide killing for executor
processes: only the recorded exact process (and executor-recorded request process group)
may be signalled. Private config/state/log/tmp directories are `0700`, the redacted log
is host-only, and only the public verification directory is mounted read-only into
Docker.

### Approval and manual authorization

Review all immutable fields in the UI, then separately confirm the matching digest in
the native macOS dialog. The native dialog is authoritative user presence; UI approval
alone does not execute. The service never captures or supplies an administrator
password, Touch ID, Keychain value, Gatekeeper choice, license acceptance, or GUI
consent. If required, the receipt identifies the remaining manual action and must not
claim an install succeeded.

### Persistence, recovery, and rollback/disable

Requests are digest-keyed, locked, monotonic, and single-use. Duplicate confirmation or
resume returns the existing terminal receipt. A restart cannot silently replay an
uncertain mutation; inspect partial state and rollback accounting, then create a new
request if needed. Rollback removes only request-created paths when the reviewed
category supports that guarantee; otherwise the receipt states uncertainty and manual
recovery.

To disable, run `stop`, then move the entire installation aside (retain it if receipts
are needed for audit) and run `start`. Never delete or edit a PID and then broadly kill
processes. Disabling host operations leaves the selected repository, autonomous Coding,
checkpoints, local Git, and non-secret receipts intact. Re-enable only by restoring a
reviewed installation or running the explicit installer again and rechecking the
persisted policy.

### No GitHub overlap

This executor cannot run `gh`, authenticated remote Git/push, SSH, credential helpers,
or Docker control, and no such credential is mounted or inherited. macOS operation
approval cannot authorize GitHub publication. Any future approved GitHub publisher is a
separate security domain, policy, confirmation, credential, and receipt lifecycle.

## Development checks

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
(cd native/ConfirmationHelper && swiftc -typecheck Sources/main.swift)
```
