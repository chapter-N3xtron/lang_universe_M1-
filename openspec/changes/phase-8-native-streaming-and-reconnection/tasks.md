## 1. Native Streaming Contract

- [ ] 1.1 Inventory the installed Agent Server, LangGraph SDK, and Agent Chat UI stream APIs and record the supported `useStream`, active-run join, `reconnectOnMount` (or native equivalent), event-ID, and replay-retention behavior.
- [ ] 1.2 Configure Jasper runs and threads to use durable Agent Server `thread_id` and native run/thread lifecycle identifiers for submit, history, active-run discovery, and stream attachment.
- [ ] 1.3 Remove or bypass the parallel Jasper chat-stream path so the conversation uses the native Agent Server stream without changing unrelated transports or UI behavior.

## 2. Server-Side Event and Access Boundaries

- [ ] 2.1 Implement server authorization for Jasper thread/run history and streams, and deny direct browser creation, joining, or streaming of Coder outside an authorized Jasper delegation.
- [ ] 2.2 Configure message, custom, and subgraph stream modes deliberately so the browser path receives Jasper user-visible messages but not raw subgraph state, model output, or tool events.
- [ ] 2.3 Implement the bounded allowlist projection for approved Coder progress, including allowed kinds/fields, size and rate bounds, sanitization, and fail-closed handling of unknown or extra data.
- [ ] 2.4 Ensure raw Coder reports, internal reasoning, prompts, tool arguments/results, credentials, environment values, and secret-bearing payloads cannot cross the browser stream boundary or become transcript messages.
- [ ] 2.5 Verify streaming and reconnection invoke the existing approval-mode default and generic inferred-routing approval path unchanged, including pending interrupts.

## 3. Browser Stream and Reconnection

- [ ] 3.1 Wire the Jasper-only conversation surface to native `useStream` with the durable thread identity and no assistant/Coder selector.
- [ ] 3.2 Implement mount-time active/resumable-run attachment with `reconnectOnMount` or the documented native equivalent, ensuring reconnect never resubmits user input.
- [ ] 3.3 Carry `Last-Event-ID` or the SDK's native cursor on supported endpoints and deduplicate replayed Jasper messages/progress by stable native identifiers.
- [ ] 3.4 Implement replay-unavailable, cursor-expired, no-active-run, and completion-race fallbacks by reconciling authoritative thread/run state without fabricating missed progress.
- [ ] 3.5 Render allowlisted Coder progress as bounded, keyed, non-transcript activity within the existing chat surface, while appending only user and Jasper user-visible messages to the transcript.
- [ ] 3.6 Decouple browser stream abort/unmount/network loss from run cancellation while preserving the existing explicit authorized cancel action and server terminal policies.

## 4. Focused Verification and Documentation

- [ ] 4.1 Add server tests proving guessed/unauthorized assistant, thread, run, and replay identifiers are denied and direct Coder access is unavailable.
- [ ] 4.2 Add wire-boundary tests with canary secrets and raw Coder/tool/report events proving only allowlisted bounded progress and Jasper messages reach the browser stream.
- [ ] 4.3 Add client/integration tests for incremental Jasper messages, disconnect during active autonomous work, reconnect without duplicate runs, completion races, replay deduplication, expired/unavailable replay fallback, and explicit cancellation.
- [ ] 4.4 Add regression tests proving reconnect does not auto-approve pending interrupts and the approval-mode default plus generic inferred-routing approval behavior remain unchanged.
- [ ] 4.5 Document the verified native reconnect mechanism, applicable `Last-Event-ID`/cursor and retention behavior, and the distinction between checkpoint durability, event replay, and authoritative state reconciliation.
- [ ] 4.6 Run the focused backend and Agent Chat UI streaming/reconnection test suites and record results without adding dashboard, speech, deployment-acceptance, MCP, persistence-schema, or report-schema work.
