# Current handoff

The coding layer is Deep Agents using its direct Python SDK. The former coding
runtime and rollback adapter have been removed after the parity gate passed.

## Stable boundaries

- The UI sends `target_agent: "coding"`, an absolute `workspace`, a provider-
  prefixed `model`, and `execution_mode` (`read_only` or `approval`).
- The coding graph returns standard LangGraph messages, state updates, tool
  events, and interrupts.
- Final LangGraph messages and state are canonical; the UI does not maintain a
  second coding transcript or custom event protocol.
- Tool events never include arguments, outputs, prompts, file contents, or raw
  exceptions.
- Durable nested sessions are scoped by user, UI thread, and resolved workspace.
- Filesystem mutation and allowlisted commands require standard HITL approval.

## Providers

- Local Ollama: `ollama/<model>`
- Ollama Cloud: `ollama-cloud/<model>`
- Hugging Face: `huggingface/<repo>` or `hf/<repo>`

See `backend/.env.example` for variable names. Never print or copy credential
values into source, tests, todos, logs, or chat.

## Verification baseline

The migration gate and its evidence are in `backend/PARITY.md`. At cutover the
backend suite, TypeScript, optimized production build, mocked browser suite,
and live read-only local-Ollama SDK smoke all passed.

The remaining measured work is UI performance remediation. Start from the
Deep Agents event path and the tasks in the `UI Lag` section of `todos.json`.
Do not reintroduce a second coding-event text transcript.

## Task tracking

`todos.json` is the sole task source of truth. Root `AGENTS.md` defines its
schema and mutation protocol. Completed entries are retained as audit history.
