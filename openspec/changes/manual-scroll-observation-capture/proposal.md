## Why

A screen recording shows what the human saw, while a timestamped JSON log shows the browser's message, viewport, and scroll measurements. The two artifacts are reviewed together.

The current browser-console workflow is unnecessarily difficult. Capture needs one visible control inside the local UI.

## What Changes

- Show **Start JSON Capture** for an existing active thread in the local app.
- Start capture from the button's normal React `onClick` handler. Nothing is entered or injected through the Brave console.
- While active, show **Capturing JSON · mm:ss** so the screen recording visibly shows the capture interval.
- Change the control to **Stop Capture** while recording.
- On Stop, use standard browser download APIs to download one JSON file containing metadata and events.
- The human saves or moves that file to `logs/scroll-observations/`, which Coding sees at `/workspace/logs/scroll-observations/`.
- Keep Playwright separate. It only verifies that the button and JSON download work.

## Manual Sequence

1. Open an existing thread.
2. Start the screen recording.
3. Press **Start JSON Capture**.
4. Exercise the conversation scrolling.
5. Press **Stop Capture**.
6. Stop the screen recording.
7. Place the JSON file in `logs/scroll-observations/` for Coding to review beside the video.

## Behavior Being Observed

The paired video and JSON observe whether:

1. reopening a thread places the latest message at the top once;
2. a new user message moves to the top once;
3. a completed assistant response moves to the top once; and
4. later human scrolling is not overridden.

The companion behavior contract remains in `../conversation-scroll-anchoring/`.

## Boundaries

No browser-console workflow, extension, userscript, custom Brave protocol, backend capture endpoint, automatic screen recording, upload service, or replay system is added.
