## Purpose

Enable deliberate GitHub repository creation and first push without exposing publishing credentials or privileged execution to autonomous Coding.

## ADDED Requirements

### Requirement: Autonomous Coding remains locally capable and uncredentialed
The system SHALL allow autonomous Coding to perform long-horizon work inside the selected repository, including local `git init`, edits, dependency commands, tests, builds, and local commits, without supplying GitHub credentials or privileged publication access to the autonomous execution environment.

#### Scenario: Autonomous local repository work
- **WHEN** the human selects autonomous Coding for a valid workspace
- **THEN** Coding can initialize and modify the local Git repository and continue long-horizon local work without a GitHub publication credential

#### Scenario: Autonomous publishing attempt
- **WHEN** autonomous shell execution attempts to create a GitHub repository or authenticate a remote push directly
- **THEN** the attempt cannot obtain a GitHub token, private key, SSH agent, credential helper, publisher credential, Docker control, or equivalent publication authority

### Requirement: Publication requests are exact and immutable
The system SHALL represent a publication request with a canonical local repository path, fixed owner `chapter-N3xtron`, repository name, human-visible visibility, source ref, exact source commit SHA, target branch, derived remote URL, exact first-push refspec, request digest, and expiry. The system SHALL reject requests whose repository is outside authorized roots, is not a valid Git repository, has an unresolved merge or rebase, has staged or unstaged changes, has untracked non-ignored files, or does not resolve the source ref to the stated commit.

#### Scenario: Valid publication request
- **WHEN** Coding requests publication from a clean authorized repository and every required field resolves consistently
- **THEN** the system presents one immutable request bound to the exact commit and proposed remote operation

#### Scenario: Dirty or inconsistent source repository
- **WHEN** the repository state, source ref, commit SHA, target ref, remote URL, or request digest does not match the proposed operation
- **THEN** the system rejects the request before GitHub credentials or remote mutation are possible

### Requirement: Publication requires explicit human approval
The system SHALL use a durable human-in-the-loop interruption for every publication request and SHALL permit only approval or rejection of the exact request. The approval presentation SHALL show the canonical local repository, `chapter-N3xtron/<name>`, public or private visibility, source commit, target branch, remote URL, first-push refspec, expiry, and the possibility of cleanup after a partial failure. Bulk approval, automatic approval, model-authored approval, and resolving an interrupt without a decision SHALL NOT authorize publication.

#### Scenario: Human approves exact request
- **WHEN** the human reviews all publication fields and explicitly approves the request through the privileged confirmation boundary
- **THEN** only that exact request becomes eligible for one publication attempt

#### Scenario: Human rejects or abandons request
- **WHEN** the human rejects the request, cancels confirmation, allows it to expire, or closes it without approval
- **THEN** no GitHub repository is created, no remote push occurs, and autonomous local work remains intact

#### Scenario: Requested fields change
- **WHEN** any approved repository name, visibility, source SHA, target branch, URL, refspec, or path changes
- **THEN** the prior approval is invalid and a new complete publication request is required

### Requirement: Publishing credentials remain in a separate security domain
The system SHALL perform authenticated GitHub operations only in a privileged execution domain that is separate from the Agent Server and autonomous Coding environment. Publication credentials, credential stores, signing keys, privileged control sockets, and writable publisher state SHALL NOT be exposed through container environment variables, mounted files, graph state, checkpoints, tool arguments, messages, logs, or repository files. A request originating from the autonomous environment SHALL NOT cause a remote mutation without contemporaneous human confirmation of the exact operation.

#### Scenario: Autonomous environment probes for authority
- **WHEN** autonomous Coding inspects its environment, mounts, process metadata, graph state, network services, or repository files
- **THEN** it cannot recover or exercise GitHub publication credentials or forge publisher authorization

#### Scenario: Direct request to privileged boundary
- **WHEN** an unapproved or replayed client calls the privileged publication boundary directly
- **THEN** the boundary performs no remote mutation without valid single-use request state and human confirmation of the matching digest

### Requirement: Publication is narrowly scoped
The privileged publisher SHALL fix the owner to `chapter-N3xtron`, create only a new repository with the approved name and visibility, and push only the approved source commit to the approved target branch using the derived refspec. It SHALL reject arbitrary owners, organizations, URLs, shell commands, additional refspecs, tags, force pushes, deletion of existing repositories, mutation of existing repositories, and any operation outside repository creation and its first push.

#### Scenario: New repository and first push succeed
- **WHEN** GitHub confirms that `chapter-N3xtron/<name>` does not exist and the exact approved operation succeeds
- **THEN** the new repository has the approved visibility and its approved target branch resolves to the approved source commit SHA

#### Scenario: Target already exists
- **WHEN** a repository with the approved owner and name already exists
- **THEN** the system does not mutate it and reports a terminal name-collision result

#### Scenario: Alternate owner or operation is proposed
- **WHEN** a request targets another owner, an existing repository, an extra ref, a force push, an arbitrary command, or a non-derived remote URL
- **THEN** the privileged publisher rejects the request without using GitHub credentials

### Requirement: Publication uses a frozen source snapshot
The privileged publisher SHALL independently resolve and stage the approved commit before remote mutation and SHALL publish only that frozen commit. Changes to the working tree, branch pointer, repository identity, or path after approval SHALL NOT alter the content published by the approved request.

#### Scenario: Source branch moves after approval
- **WHEN** the source branch advances or the working tree changes after approval
- **THEN** the publisher either publishes only the previously approved frozen commit or aborts and requires a new approval; it never silently publishes the newer state

#### Scenario: Source object is unavailable
- **WHEN** the approved commit cannot be independently resolved and staged
- **THEN** publication stops before repository creation

### Requirement: Requests are single-use, durable, and idempotent
The system SHALL persist non-secret request status across graph, UI, publisher, and process restarts. A request digest SHALL be single-use, concurrent execution SHALL be prevented, and retries SHALL return the existing terminal result rather than creating another repository or repeating a successful push.

#### Scenario: Duplicate approval or resume
- **WHEN** the same request is approved, resumed, retried, or delivered more than once
- **THEN** at most one repository creation and one first push are attempted and all callers receive the same terminal receipt

#### Scenario: Restart while approval is pending
- **WHEN** the UI, Agent Server, or privileged publisher restarts before a decision
- **THEN** the exact pending request remains reviewable without gaining approval or losing its expiry

### Requirement: Publication produces a durable redacted receipt
The system SHALL return and retain a verifiable non-secret receipt containing the request digest, terminal status, timestamps, canonical owner/name, GitHub repository ID and URL when available, visibility, source SHA, target ref, verified remote SHA when available, and failure or cleanup status. Receipts and logs SHALL exclude tokens, authorization headers, private keys, credential-helper output, secret environment values, and unrelated repository content.

#### Scenario: Successful receipt
- **WHEN** repository creation and first push are verified
- **THEN** Coding and the human receive a durable receipt showing that the remote target resolves to the approved SHA

#### Scenario: Rejected or failed receipt
- **WHEN** publication is rejected, expires, fails, or is partially completed
- **THEN** the receipt clearly distinguishes the terminal state and contains no credential material

### Requirement: Partial failures are contained and disclosed
The approval presentation SHALL disclose that GitHub repository creation and first push are separate external operations. If creation succeeds and first push fails, the privileged publisher SHALL attempt only the pre-approved cleanup of the newly created repository, SHALL never delete a pre-existing repository, and SHALL record whether cleanup succeeded. The system SHALL NOT claim atomic rollback when GitHub or the network prevents verification or cleanup.

#### Scenario: Push fails after creation
- **WHEN** the publisher created the new repository but cannot complete or verify the approved first push
- **THEN** it attempts cleanup only for the repository created by that request and reports the exact partial-failure and cleanup outcome

#### Scenario: Cleanup cannot be verified
- **WHEN** GitHub or network failure prevents confirmed cleanup
- **THEN** the receipt warns that the remote repository may remain and requires human review rather than reporting success or full rollback
