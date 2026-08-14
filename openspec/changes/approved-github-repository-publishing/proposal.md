## Why

Coder must remain capable of long-horizon autonomous repository work while GitHub repository creation and first push remain deliberate human actions. The current shared Agent Server cannot safely hold GitHub credentials because documented `LocalShellBackend` execution is not confined, so autonomous shell work and privileged publishing need separate security domains.

## What Changes

- Keep autonomous Coding uncredentialed and able to perform local repository work, including `git init`, edits, tests, builds, and local commits.
- Add a credential-isolated publishing boundary for creating a repository only under `chapter-N3xtron` and performing its first push.
- Require a human approval that shows the exact local repository, GitHub owner/name, visibility, source ref, remote URL, and proposed first-push operation before credentials can be used.
- Make each approval single-purpose and bounded to the reviewed operation; rejection, cancellation, expiry, or changed inputs must not publish anything.
- Return a durable, non-secret receipt describing the approved request and verified GitHub result.
- Keep GitHub credentials, private keys, credential files, Docker control, and privileged executor access unavailable to autonomous Coding.
- Use documented LangGraph human-in-the-loop behavior for review and resumption; do not add model-authored approval, automatic approval, or a second agent reasoning layer.

## Capabilities

### New Capabilities
- `approved-github-repository-publishing`: Credential-isolated, human-approved creation of a GitHub repository under `chapter-N3xtron` and its first push while autonomous Coding remains uncredentialed.

### Modified Capabilities

None.

## Impact

- Coding completion and publication-request contracts in the backend.
- LangGraph approval presentation and durable resume behavior.
- A separately isolated GitHub publication executor and its deployment configuration.
- UI approval details, rejection/cancellation handling, and publication receipts.
- GitHub credential provisioning, redaction, audit records, security documentation, and end-to-end tests.
