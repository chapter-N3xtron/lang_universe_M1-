## 1. Report artifact contract

- [ ] 1.1 Add a strict, versioned `coder_report` visual-artifact schema beside the existing `react_flow` artifact schema. Define its report snapshot, per-file change counts, diff availability states, bounded diff payload, and unsupported-version handling.
- [ ] 1.2 Keep `TechnicalReport` as the authoritative Coder-to-Jasper handoff. Add deterministic conversion from a validated terminal report to exactly one report artifact, with no model-generated report or diff content.
- [ ] 1.3 Add contract tests for valid completed, partial, blocked, failed, and cancelled report artifacts; rejected extra or unsupported fields; unsafe paths; invalid counts; missing required report content; and unsupported artifact versions.

## 2. Safe Coder diff capture

- [ ] 2.1 Capture changed-file status, repository-relative path, and added/removed line counts from the explicitly selected Coder workspace after terminal Coder work.
- [ ] 2.2 Capture only safe bounded before/after content or patches required for visual diff presentation. Preserve an explicit unavailable reason for binary, unavailable, redacted, or budget-excluded files.
- [ ] 2.3 Apply existing sensitive-output redaction before an artifact is persisted or returned to the browser. Enforce the existing total visual-artifact size ceiling without silent omission.
- [ ] 2.4 Add focused tests for normal text changes, added/deleted/renamed files, unavailable source, binary data, secret-like content, oversized candidate diffs, correct line counts, and no source content outside the selected workspace.

## 3. Existing handoff and persistence path

- [ ] 3.1 Attach the deterministic report artifact to the existing valid Coder-to-Jasper return result and the existing `visual_artifacts` session state, without changing graph registration, streaming, speech transport, or approval behavior.
- [ ] 3.2 Confirm the existing session artifact persistence path stores and reloads report artifacts without a new database table or artifact store.
- [ ] 3.3 Update the existing visual-artifact validation boundary so report artifacts and concept-map artifacts are both accepted and invalid artifacts fail closed.
- [ ] 3.4 Add integration coverage proving a Coder terminal result produces one persisted report artifact and that invalid reports create neither a technical artifact nor a completion assertion.

## 4. Library-based visual board presentation

- [ ] 4.1 Install `@radix-ui/react-tabs` and `@pierre/diffs` with pnpm. Record the locked versions and avoid adding a custom tab or diff engine.
- [ ] 4.2 Add a report-artifact renderer in the existing session visual pane. Use Radix Tabs for the technical Report tab and changed-file tabs, with visible selected state and documented keyboard navigation. Add the read-only documented `@pierre/trees/react` changed-file tree to the Report tab with built-in Git-status records; selecting a tree path opens its existing file-diff tab.
- [ ] 4.3 Label each file trigger with its repository-relative path and `−removed +added` counts. Render the active available file with `@pierre/diffs/react` and its documented virtualization container; render a clear unavailable explanation when a diff is not safely stored.
- [ ] 4.4 Preserve the current React Flow concept-map renderer and timeline behavior while allowing either artifact type to be selected.
- [ ] 4.5 Add focused frontend coverage for report details, file-tab selection, code-diff rendering, unavailable-diff display, keyboard tab navigation, large bounded diff virtualization, version limitation display, and unchanged concept-map rendering.

## 5. Jasper walkthrough and verification

- [ ] 5.1 Preserve Jasper's existing `JasperResponse.voice_text` handoff. Ensure it gives the complete plain-language report walkthrough while never speaking raw code, patches, tab labels, or exhaustive file lists.
- [ ] 5.2 Add regression coverage proving report artifacts do not add or change text-to-speech endpoints, browser-sidecar transport, streaming, approval mode, or repository mutation capability.
- [ ] 5.3 Run OpenSpec validation; the focused report-contract, Coder capture, Jasper handoff, backend artifact persistence, and frontend renderer tests; then run the production frontend build. Record source-level results without claiming deployed acceptance.
- [ ] 5.4 Before declaring deployed behavior, rebuild the `jasper-langgraph:current` image, recreate the relevant containers, and verify the port-3002 frontend against the canonical Docker-backed Agent Server. Clearly distinguish this deployed check from source tests.
