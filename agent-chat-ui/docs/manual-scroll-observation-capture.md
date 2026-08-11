# Temporary manual scroll-observation capture

This is a **development-only, explicitly opt-in** smoke-test aid. It is not
production telemetry, a replay harness, a dashboard, or a replacement for the
conversation scroll assertions.

## Activation and one named session

1. Start the dev server (`pnpm dev`) and open the conversation with
   `?manualScrollCapture=1` appended to the URL. The query flag is required;
   ordinary development has no capture API and production is a no-op.
2. There is currently no visible human-facing control or terminal command. In
   the browser console, start a named scenario and explicitly provide the
   thread ID when thread correlation is needed:

   ```js
   window.manualScrollObservation.start({
     scenarioId: "reopen-stream-manual-scroll",
     threadId: "<explicit thread id>",
   });
   ```

   `threadId` is session metadata, not automatically discovered from LangGraph
   Studio or application state. A URL `threadId` value is only an explicit
   fallback; do not assume the logger can discover the active thread.

   The confirmation warns that rendered message content will be captured. Do
   not use real secrets or sensitive conversations for this isolated test.
3. Start QuickTime Screen Recording manually. This app does not start, stop, or
   save the movie. Optionally pair its details in the console:

   ```js
   window.manualScrollObservation.setRecording({
     filename: "reopen-stream-manual-scroll.mov",
     path: "<local path, if useful>",
     startTime: new Date().toISOString(),
     notes: "Started manually after the browser confirmation",
   });
   ```

4. Exercise the named human scenario. The active session observes rendered
   messages, explicit thread/message IDs, anchors, geometry, viewport metrics,
   scroll/user and diagnostic programmatic calls, bounded mutation/resize
   summaries, and visible UI state. It is local/in-memory, opt-in, bounded to
   2,000 events, and limits each captured content string to 12,000 characters.
5. Stop QuickTime manually, add its end time, then stop the logger:

   ```js
   window.manualScrollObservation.setRecording({
     endTime: new Date().toISOString(),
   });
   window.manualScrollObservation.stop();
   ```

   The browser downloads `<session>.json` (bundle with events and manifest) and
   `<session>.manifest.json`. Keep these temporary local files beside the `.mov`
   and delete all three after review. `discard()`/`delete()` remove the
   in-memory session before download, but a web page cannot delete files already
   placed in the browser Downloads folder. There is no automatic retention or
   deletion.

Other controls are `pause()`, `resume()`, `status()`, `redact(text)`, and
`discard()` (with `delete()` as the in-memory discard alias). Pause/stop/discard
are voluntary and do not affect the conversation. If download finalization
fails, the manifest reports the error; the page cannot guarantee cleanup of
browser-managed downloads.

## Capture and privacy boundary

The logger reads only rendered observation-boundary data: `[data-message-id]`
content and geometry, conversation viewport metrics, anchor IDs, DOM mutation
summaries, resize observations, scroll calls, and visible UI-state fields.
Streaming/fallback/error values are snapshot observations; hydration, recovery,
and layout settlement can be `null` because no automatic transition detector is
installed.

It never reads or records credentials, cookies, authorization headers, tokens,
private keys, environment-file contents, network payloads, browser storage,
unrelated page data, or internal model reasoning. Captured text is truncated and
passed through heuristic denylist rules for private-key blocks, bearer/basic
credentials, common secret/token/auth/cookie assignments, token query
parameters, and selected environment-style assignments. Redaction is not a
secret-detection guarantee; inspect the temporary files before sharing.

## Reading evidence

Use `started_at`, `ended_at`, `elapsed_ms`, and `wall_time` to align the JSON
timeline beside the separately recorded video. The log is structured observed
browser evidence; the video shows pixels and human-visible timing, but cannot
reliably reveal DOM identity, exact scroll metrics, hidden content, mutation
causes, or whether movement was programmatic. Treat visual interpretation as
observed/inferred and do not claim the bundle proves anchoring correctness.

The manifest contains `review: null` intentionally: no model/video processing,
remote review, upload, or automated interpretation is enabled. Visible UI,
terminal launch, automatic thread-ID discovery, robust downloaded-artifact
retention/deletion, and full automated browser/deletion validation remain future
work or validation gaps.
