# UI performance baseline

Measured from the optimized production build on 2026-07-30 with Chromium.

## Budgets

| Scenario                         | Budget     | Baseline |
| -------------------------------- | ---------- | -------- |
| 300-message thread ready         | < 2,500 ms | 378 ms   |
| Initial visible message rows     | <= 80      | 80       |
| Initial DOM nodes                | < 5,000    | 1,914    |
| Maximum initial long task        | < 250 ms   | 0 ms     |
| Initial JS heap                  | < 150 MiB  | 24.5 MB  |
| 128-event coding stream complete | < 2,500 ms | 447 ms   |
| Maximum stream long task         | < 250 ms   | 54 ms    |
| Maximum stream frame interval    | < 200 ms   | 59 ms    |
| Sample historical-row rerenders  | 0          | 0        |

The regression is `tests/performance.spec.ts`. It runs against the production
server, injects a 300-message persisted thread, then sends the maximum bounded
coding-event stream (128 events, including 16 KiB of batched transient text).

## Remediation applied

- Native coding events are capped at 128 per run; transient text is batched at
  512 characters and capped at 16 KiB. The browser retains only 32 events.
- Historical message rows no longer read the stream context for metadata and
  actions. Only the active interrupt/external-component leaf subscribes when
  present. The composer receives stable action wrappers instead of subscribing
  to every token/event.
- Threads render the newest 80 messages and expose an accessible control to
  reveal earlier 80-message windows. A window boundary expands backward over
  tool results so the visible list does not begin mid-tool sequence.
- Streaming assistant text uses a plain whitespace-preserving element. Final
  Markdown is memoized; syntax highlighting and math/Katex load only when the
  content needs them.
- Main sidebar/header movement uses short CSS transitions with
  `prefers-reduced-motion` support instead of spring animation work.
- The first-load route fell from 676 kB before remediation to 549 kB after
  code/math splitting and layout cleanup.

Run the profile separately from functional browser tests:

```bash
./node_modules/.bin/playwright test tests/performance.spec.ts --reporter=line
```
