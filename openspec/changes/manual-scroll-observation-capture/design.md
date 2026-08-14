## Design

The capture control is part of the local React UI:

```text
Start screen recording
        ↓
Press Start JSON Capture
        ↓
React onClick starts the bundled recorder
        ↓
UI shows Capturing JSON · mm:ss
        ↓
Press Stop Capture
        ↓
Brave downloads one JSON file
```

No JavaScript is pasted into or injected through the Brave console. The button calls code already bundled with the page.

## Control

- Show the control only on `localhost` or `127.0.0.1`.
- Enable Start only when the UI has an active `threadId`.
- Pass that `threadId` directly from existing application state to the recorder.
- Show a red capture indicator and elapsed time while active.
- Expose only Start and Stop in the UI.

## JSON Download

Stop creates one JSON bundle containing:

- session and thread identifiers;
- start and stop timestamps;
- ordered browser observations; and
- final capture status.

The page serializes the bundle to a `Blob`, creates a blob URL with `URL.createObjectURL()`, and uses an anchor's `download` property to ask Brave to download it. The page then revokes the blob URL.

Brave controls the final download location. The human saves or moves the file to:

```text
/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/logs/scroll-observations/
```

Coding reads the same folder at:

```text
/workspace/logs/scroll-observations/
```

## Video Relationship

The human starts screen recording before pressing Start JSON Capture. The visible timer makes the JSON capture interval clear in the video. The app does not control the screen recorder.

The video shows visible behavior. JSON supplies timestamps and browser measurements. They are reviewed together as evidence; capture does not decide pass or fail by itself.

## Playwright Relationship

Playwright is not used during manual recording. A small automated test separately clicks Start and Stop, waits for the download event, and verifies that the JSON is parseable and contains observations.

## Documentation Basis

- React documents normal button event handlers with `onClick`: https://react.dev/learn/responding-to-events
- MDN documents the widely available anchor `download` property: https://developer.mozilla.org/en-US/docs/Web/API/HTMLAnchorElement/download
- MDN documents `URL.createObjectURL()` for `Blob` URLs and `URL.revokeObjectURL()` cleanup: https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static
- Brave documents normal file downloads and changing download locations: https://support.brave.com/hc/en-us/articles/360018192491-How-do-I-fix-file-download-errors
- Playwright documents waiting for a page download and reading or saving it: https://playwright.dev/docs/downloads

## Excluded Complexity

Do not add a console API, browser extension, userscript, custom protocol, file-picker API, backend writer, upload service, or automatic video control.
