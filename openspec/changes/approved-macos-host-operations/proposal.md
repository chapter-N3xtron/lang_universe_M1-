## Why

Coder can autonomously edit the selected Mac-host repository through a Docker bind mount, but its shell runs inside Linux and cannot truthfully inspect or modify macOS. macOS-only work such as Blender installation, Homebrew operations, DMG handling, and `/Applications` changes needs an explicit host boundary without giving autonomous Coding unrestricted access to the Mac.

## What Changes

- Preserve autonomous long-horizon repository work in the uncredentialed Linux container.
- Keep the exact human-selected repository as the workspace; never search sibling repositories or substitute another repository when the selected path is empty or not yet initialized.
- Make the execution environment visible so Jasper and Coder distinguish Mac-host files from Linux-container commands.
- Add a separate macOS host executor for narrowly typed host inspection, download, package, application-installation, and application-invocation actions.
- Require human approval of the exact host action plan, argv, paths, downloads, expected mutations, privileges, timeout, and rollback limits before host execution.
- Keep host environment secrets, Keychain, private keys, credentials, arbitrary shell access, and executor authority unavailable to autonomous Coding.
- Return durable, redacted host-operation receipts to Coder so autonomous repository work can continue after approval, rejection, failure, or restart.
- Use documented LangGraph human-in-the-loop interruption and resume behavior without adding another reasoning agent or changing the existing Coding graph topology.

## Capabilities

### New Capabilities
- `approved-macos-host-operations`: Human-approved, credential-isolated macOS operations supporting autonomous containerized Coding against an exact Mac-host repository.

### Modified Capabilities

None.

## Impact

- Workspace selection and thread-state persistence.
- Jasper-to-Coding handoff language and environment reporting.
- Coding tool configuration and documented HITL requests.
- A separate non-agent macOS host executor and launcher lifecycle.
- Approval UI, host-native confirmation, receipts, restart behavior, and audit records.
- Security, deployment, browser, backend, and adversarial tests.
