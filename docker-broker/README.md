# Docker Broker

A standalone, loopback-only macOS service for policy-constrained Docker Compose operations. Docker daemon authority remains on the host and is never mounted into LangGraph.

The broker includes a Coder-facing confirmation flow. It verifies the exact pending LangGraph interrupt directly against a fixed loopback Agent Server, derives the workspace from checkpoint state, and still requires native macOS approval before creating an in-memory lease.

## Authority model

- A native macOS dialog approves one `(thread_id, owner_id, Git repository)` scope. The Coder flow pins `owner_id` in host configuration for a single user; it does not accept owner identity from the browser or model.
- Approval creates an opaque, in-memory lease with a bounded lifetime.
- The lease token must remain in a trusted host client. Never put it in model messages, LangGraph state, logs, or repository files.
- Every HTTP request also requires the host client secret stored at `<state-directory>/client-secret` with mode `0600`.
- Revocation terminates an active broker subprocess group. Containers already started can continue running.
- Broker state must not overlap an allowed repository.

## Enforced Compose subset

The broker accepts exactly one Compose file and validates both the source document and Docker Compose's canonical JSON model. It executes only a broker-owned immutable snapshot.

Allowed workloads are intentionally narrower than general Compose:

- Services must use a `sha256` digest image reference.
- Repository builds are disabled by default and are enabled only with `--allow-builds`. The existing isolated BuildKit policy remains in force; the flag does not enable additional Docker commands or widen the Compose policy.
- Published ports must explicitly bind to `127.0.0.1` and must avoid reserved Jasper ports.
- Storage is limited to project-declared named volumes and container `tmpfs` mounts.
- Networks are project-local bridge networks; only the `internal` option is accepted.
- Container CPU, memory, and PID limits are broker-enforced.
- Restart behavior is limited to `no` or bounded `on-failure`.

Rejected features include builds unless explicitly enabled, bind mounts, Docker sockets, privileged mode, devices, added capabilities, host namespaces, external/custom networks or volumes, volume driver options, Compose `extends`/`include`, YAML aliases, service `env_file`, configs/secrets, multi-file overlays, unbounded deployment scaling, and destructive volume deletion.

Implicit project `.env` loading is disabled. Compose control variables are pinned by the broker. Environment values embedded in the validated Compose document remain workload data and are not returned or audited.

Project snapshots reject symlinks, hard links, special files, more than 20,000 entries, more than 500 MB, and directory depth over 64. `.git` is excluded. Named volumes persist across operations; `down` does not delete volumes. Keep the validated Compose file available for broker-mediated teardown; source deletion or invalidation currently requires explicit operator cleanup.

## Run

```sh
cd docker-broker
uv sync
uv run pytest -q
uv run docker-broker \
  --allowed-root /absolute/git/repository \
  --state-directory "$HOME/.jasper/docker-broker" \
  --agent-server-url http://127.0.0.1:8123 \
  --owner-id local-user
```

The service defaults to `127.0.0.1:8766`. API documentation endpoints are disabled. `--agent-server-url` accepts only a numeric-loopback HTTP base URL. `--lease-seconds` defaults to 14400 and is bounded to 300–43200 seconds. Builds remain off unless `--allow-builds` is supplied.

The existing manual API remains available: supply the client secret as `X-Broker-Client-Secret` on every manual request, and use `Authorization: Bearer <lease-token>` for lease-protected requests. The Coder endpoints never return either credential. Their authority comes only from exact pending-interrupt verification followed by native approval, with an active lease reused for the same thread, pinned owner, and workspace. Browser CORS is limited to explicit `localhost` and `127.0.0.1` origins on ports 3001 and 3002.

Primary endpoints:

- `GET /health` (Coder/public health)
- `POST /v1/coder/confirmations`
- `GET /v1/coder/status/{operation_digest}`
- `GET /v1/coder/results/{operation_digest}`
- `GET /v1/health` (manual)
- `POST /v1/sessions/activate`
- `POST /v1/sessions/revoke`
- `POST /v1/compose/inspect`
- `POST /v1/compose/apply`
- `GET /v1/runtime/langgraph`

Manual activation remains rate-limited and always requires the native confirmation dialog. Coder activation also uses that dialog but does not expose the client secret or lease token to LangGraph or the browser.
