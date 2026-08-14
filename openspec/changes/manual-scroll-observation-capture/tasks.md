## Existing Recorder

- [x] Capture bounded timestamped browser observations.
- [x] Redact rendered content and keep capture local.
- [x] Download JSON from the browser.

The console prototype is not the final control surface.

## Pending UI Change

- [x] 1. Add **Start JSON Capture** / **Stop Capture** to the local conversation UI using a normal React `onClick` handler. Do not expose a public console API. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [x] 2. Pass the active `threadId` from existing UI state and disable capture when no thread is active.
- [x] 3. Show **Capturing JSON · mm:ss** with a visible red indicator while active. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [x] 4. On Stop, download one JSON file containing metadata and events using `Blob`, `URL.createObjectURL()`, and one anchor download.
- [x] 5. Remove the separate manifest download and the required browser-console workflow.
- [x] 6. Update the manual instructions: start video, press Start, exercise scrolling, press Stop, stop video, and place JSON in `logs/scroll-observations/`.
- [x] 7. Add one focused Playwright test for Start, Stop, the visible timer, and one parseable JSON download.
- [x] 8. Run one manual Brave smoke test and confirm Coding can read the JSON at `/workspace/logs/scroll-observations/`.
- [ ] 9. Review the video and JSON against reopen placement, new-user placement, completed-assistant placement, and preservation of human scrolling.

## Excluded

No URL flag, console injection, extension, userscript, file-picker API, backend writer, upload service, automatic screen recording, dashboard, or replay system.
