# Deep Agents parity gate

Validated on 2026-07-30 before removing the former rollback path.

| Capability | Evidence | Result |
| --- | --- | --- |
| Read-only repository analysis | Live direct-SDK probe read `README.md` with local `qwen3.5:27b`; 55 message chunks and 59 tool events | Pass |
| Workspace confinement and bounded edits | `test_coding_agent.py`, `test_coding_security.py` | Pass |
| Approved test execution | Allowlisted argv-only command tests with bounded time/output and redaction | Pass |
| Multi-turn and restart resume | SQLite close/reopen tests for conversation and pending HITL state | Pass |
| Subagent delegation | Deep Agents default `general-purpose` task subagent plus sanitized subagent event category | Pass |
| Long-context compaction | Deep Agents default `SummarizationMiddleware` is present in the installed SDK stack | Pass (structural) |
| Model switching | Deterministic local Ollama, Ollama Cloud, and Hugging Face provider tests | Pass |
| Approval, edit, reject, expiry | Standard HITL interrupt tests | Pass |
| Cancellation and invalid workspace | Wrapper cancellation/timeout and validation tests | Pass |
| Missing provider/dependency details | Sanitized stable error-code tests; no exception or credential values reach UI events | Pass |
| Restart persistence and isolation | Scoped session, export, reset, and restart tests | Pass |
| Streaming responsiveness | 512-character text batching, 16-KiB transient-text cap, 128 backend-event cap, 32 frontend-event cap | Pass |

Gate commands and results:

- Backend focused lint: pass.
- Backend tests: 99 passed.
- TypeScript `tsc --noEmit`: pass.
- Next.js optimized production build: pass (existing lint warnings remain documented by the UI profile).
- Mocked production UI/TTS Playwright suite: 9 passed.
- Live read-only local-Ollama Deep Agents SDK smoke: pass.

Cloud Ollama and Hugging Face are validated at their construction and routing
boundaries without spending remote quota or reading credential values. They use
the same LangChain chat-model interface exercised by the local live smoke.
