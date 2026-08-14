## Purpose

Provide one visible local UI control that creates a timestamped JSON observation log to accompany a separately recorded video.

Review `../../../conversation-scroll-anchoring/` for the behavior being observed.

## ADDED Requirements

### Requirement: Visible local capture control

The conversation UI SHALL show **Start JSON Capture** on `localhost` and `127.0.0.1` when an active thread exists. It SHALL NOT require a URL flag, browser console, DevTools injection, extension, userscript, or custom Brave protocol.

#### Scenario: Existing thread is open

- **WHEN** the local UI has an active `threadId`
- **THEN** Start JSON Capture SHALL be enabled

#### Scenario: No active thread exists

- **WHEN** no active `threadId` exists
- **THEN** capture SHALL remain disabled with a short explanation

#### Scenario: Remote deployment is open

- **WHEN** the UI is not hosted on localhost or 127.0.0.1
- **THEN** the capture control SHALL not appear

### Requirement: Button calls bundled recorder

The Start button SHALL use a normal React `onClick` handler to call the recorder bundled with the page. The current `threadId` SHALL be passed from existing application state. The target workflow SHALL NOT install a public `window` capture controller.

#### Scenario: Human starts capture

- **WHEN** the human presses Start JSON Capture and accepts the content warning
- **THEN** one in-memory capture session SHALL start for the active thread

### Requirement: Visible video marker

While capture is active, the UI SHALL show **Capturing JSON · mm:ss** with a visible red indicator. The indicator SHALL appear only after capture starts and disappear after Stop is pressed.

The app SHALL NOT claim to start or stop the screen recorder. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

#### Scenario: Screen recording is already running

- **WHEN** the human presses Start JSON Capture
- **THEN** the video SHALL visibly show the start action and active capture timer

#### Scenario: Human stops capture

- **WHEN** the human presses Stop Capture
- **THEN** the video SHALL visibly show the stop action and the JSON SHALL contain start and stop timestamps

### Requirement: One JSON download

Stop SHALL create one JSON file containing session metadata, the active thread identifier, start/stop timestamps, final capture status, and ordered events. The implementation SHALL use a `Blob`, `URL.createObjectURL()`, one anchor download, and `URL.revokeObjectURL()` cleanup.

Brave SHALL retain control over download completion, filename, and location. The UI SHALL not claim to know the final path.

#### Scenario: Brave permits the download

- **WHEN** the human presses Stop Capture and bundle creation succeeds
- **THEN** the page SHALL offer exactly one parseable JSON file

#### Scenario: Bundle creation fails

- **WHEN** the JSON bundle cannot be created
- **THEN** the UI SHALL show an error and SHALL not claim that a file was saved

### Requirement: Coding can receive the artifact

Documentation SHALL tell the human to save or move the JSON file to:

`/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/logs/scroll-observations/`

It SHALL identify the Coding-container path as:

`/workspace/logs/scroll-observations/`

The app SHALL NOT add a backend writer or upload endpoint for this workflow.

#### Scenario: JSON is placed in the shared folder

- **WHEN** the human places the file in the documented host folder
- **THEN** Coding SHALL be able to read it through the documented container path

### Requirement: Bounded observations

The JSON SHALL contain ordered timestamped observations of rendered message identifiers/content, viewport and message geometry, scroll position, user scrolls, programmatic scroll calls, DOM changes, and resize changes. Capture SHALL remain bounded to 2,000 events and 12,000 characters per captured content string.

Rendered content SHALL be captured only after confirmation and SHALL pass through the existing redaction rules. Capture SHALL exclude credentials, cookies, authorization headers, browser storage, network payloads, environment files, and internal model reasoning. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

#### Scenario: Conversation changes during capture

- **WHEN** messages render or scrolling/layout changes occur
- **THEN** the recorder SHALL append bounded timestamped observations

### Requirement: Evidence target remains clear

The paired video and JSON SHALL be described as evidence for these four behaviors:

1. reopening a thread places the latest message at the top once;
2. a new user message moves to the top once;
3. a completed assistant response moves to the top once; and
4. later human scrolling is not overridden.

Capture SHALL not modify those behaviors or claim that JSON alone proves correctness.

#### Scenario: Reviewer receives both artifacts

- **WHEN** the video and JSON are reviewed
- **THEN** visible behavior SHALL be compared with timestamped browser measurements

### Requirement: Playwright remains separate

Playwright SHALL separately verify that Start and Stop work and that one parseable JSON download contains observations. Playwright SHALL NOT be required during the human Brave recording.

#### Scenario: Automated regression runs

- **WHEN** Playwright clicks Start and Stop
- **THEN** it SHALL wait for the download and validate the JSON structure

#### Scenario: Human records in Brave

- **WHEN** the manual video and JSON session runs
- **THEN** no Playwright process SHALL be required

## Documentation References

- React `onClick`: https://react.dev/learn/responding-to-events
- MDN anchor download: https://developer.mozilla.org/en-US/docs/Web/API/HTMLAnchorElement/download
- MDN blob object URLs: https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static
- Brave downloads: https://support.brave.com/hc/en-us/articles/360018192491-How-do-I-fix-file-download-errors
- Playwright downloads: https://playwright.dev/docs/downloads
