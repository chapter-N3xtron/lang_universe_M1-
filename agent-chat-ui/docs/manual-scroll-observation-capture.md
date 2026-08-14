# Manual scroll-observation capture

This local-only tool creates one timestamped JSON log to review beside a separate screen recording. It is evidence for conversation-scroll investigation, not production telemetry or automatic proof of correctness.

## Record one session

1. Open an existing thread at `http://localhost:3001`. The thread must already have an ID.
2. Start QuickTime Screen Recording.
3. Press **Start JSON Capture** in the top bar and accept the rendered-content warning.
4. Confirm that the red **Capturing JSON · mm:ss** indicator is visible in the video.
5. Exercise the conversation behavior being investigated.
6. Press **Stop Capture**, then stop QuickTime.
7. Brave downloads one `scroll-observation-*.json` file. Save or move it to:

   ```text
   /Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/logs/scroll-observations/
   ```

   Coding can read the same file at:

   ```text
   /workspace/logs/scroll-observations/
   ```

The page does not start QuickTime and cannot know where Brave ultimately saves the file. No browser-console command, URL flag, extension, or injected script is required.

## Behavior under observation

Review the video and JSON together to determine whether:

1. reopening a thread places the latest message at the top once;
2. a newly submitted user message moves to the top once;
3. a completed assistant response moves to the top once; and
4. later human scrolling is not overridden.

## Capture boundary

The JSON contains bounded timestamps, rendered message IDs/content, anchor and message geometry, viewport metrics, scroll positions, user and programmatic scroll events, DOM changes, resize observations, and visible UI state.

Capture is limited to 2,000 events and 12,000 characters per captured content string. Rendered text passes through heuristic redaction, but redaction is not guaranteed. Do not use secrets in the test thread, review the JSON before sharing, and delete the temporary video and JSON after review.

The recorder does not read credentials, cookies, authorization headers, browser storage, network payloads, environment files, or internal model reasoning.
