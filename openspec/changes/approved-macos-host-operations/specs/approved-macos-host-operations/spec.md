## Purpose

Enable explicit, human-approved macOS operations while autonomous Coding remains containerized, uncredentialed, and bound to the exact selected Mac-host repository.

## ADDED Requirements

### Requirement: The exact selected repository is authoritative
The system SHALL preserve the human-selected canonical repository path in thread state and SHALL give that exact path to Jasper and Coding. An existing empty directory SHALL remain a valid selected workspace even before `git init`. The system SHALL NOT search sibling directories, substitute another repository, fall back to the home directory, or reinterpret a host path as `/workspace`.

#### Scenario: Empty selected repository
- **WHEN** the human selects an existing empty directory such as `/Users/chaptercaptaingeneral/programatic_3d_rendering`
- **THEN** Coding works only in that directory and may initialize Git there without selecting another child or sibling repository

#### Scenario: Selected path becomes unavailable
- **WHEN** the saved selected path no longer exists or resolves outside the authorized host roots
- **THEN** the request stops with a visible workspace error and no substitute workspace is chosen

#### Scenario: Thread resumes
- **WHEN** the thread is refreshed, reopened, interrupted, or resumed
- **THEN** the canonical selected repository remains unchanged until the human explicitly selects a different path

### Requirement: The execution boundary is reported truthfully
The system SHALL distinguish the host filesystem from the command runtime in every Coding handoff and result. Containerized commands SHALL be identified as Linux-container execution even when they read or write files physically stored on macOS. Jasper and Coding SHALL NOT describe container commands as Mac-host commands or claim that a macOS application or system location changed when only the container changed.

#### Scenario: Container inspects its operating system
- **WHEN** Coding runs `uname`, package-manager discovery, process inspection, or system installation commands in the Agent Server container
- **THEN** the result identifies the Linux-container runtime and separately identifies the selected Mac-host repository mount

#### Scenario: Task requires macOS
- **WHEN** a task requires `sw_vers`, Homebrew, DMG mounting, `/Applications`, Finder, Keychain, launch services, or a native Mac application
- **THEN** Coding requests an approved macOS host operation rather than attempting a Linux substitute or declaring that the physical Mac was modified

### Requirement: Autonomous repository work remains containerized
The system SHALL preserve autonomous long-horizon Coding for repository-local reads, writes, local `git init`, local commits, dependency commands, tests, and builds in the selected repository. Autonomous Coding SHALL NOT receive general Mac-host shell access or macOS executor authority.

#### Scenario: Long-horizon local work
- **WHEN** the requested work can be completed using repository files and the Linux toolchain
- **THEN** Coding continues autonomously without host-operation approval prompts

#### Scenario: Host-only boundary is reached
- **WHEN** autonomous work reaches a step requiring macOS state or a native application
- **THEN** local progress is preserved and one bounded host-operation request is presented without granting autonomous host execution

### Requirement: Host-operation requests are typed and immutable
The system SHALL represent each host-operation request with a canonical action category, executable identity, argv list, canonical working directory, input and output paths, download URLs and expected integrity evidence when applicable, content hashes for executable scripts or configuration, expected host mutations, required privileges, timeout, rollback limits, request digest, and expiry. The system SHALL reject shell command strings, shell metacharacter interpretation, unbounded environment inheritance, unresolved paths, symlink escapes, and fields that cannot be independently canonicalized.

#### Scenario: Valid Blender installation request
- **WHEN** Coding proposes a native Blender download or installation with exact official URL, destination, checksum evidence, application path, argv, mutations, timeout, and rollback limits
- **THEN** the human receives one immutable request bound to those exact values

#### Scenario: Request contains arbitrary shell execution
- **WHEN** a request uses `sh -c`, `bash -c`, command substitution, redirection, pipelines, arbitrary interpreters, unreviewed scripts, unresolved executables, or model-provided environment variables
- **THEN** the request is rejected before host execution

#### Scenario: Reviewed script changes
- **WHEN** a repository script or configuration referenced by an approved host action no longer matches its approved content hash
- **THEN** the prior approval is invalid and a new request is required

### Requirement: Every macOS host operation requires explicit human approval
The system SHALL use a durable human-in-the-loop interruption for each host-operation request. The approval presentation SHALL show the exact action category, executable, argv, working directory, affected paths, downloads and provenance, script hashes, expected mutations, privilege level, timeout, rollback limits, and execution environment. Bulk approval, generic resolve behavior, model-authored approval, implicit approval, and approval of changed fields SHALL NOT authorize host execution.

#### Scenario: Human approves exact action
- **WHEN** the human reviews the complete immutable action and confirms it through the host user-presence boundary
- **THEN** only that exact action becomes eligible for one execution attempt

#### Scenario: Human rejects or abandons action
- **WHEN** the human rejects, cancels, closes, or allows the request to expire
- **THEN** no Mac-host command runs and autonomous repository work remains intact

#### Scenario: Action plan changes
- **WHEN** any executable, argv element, path, URL, hash, mutation, privilege, timeout, or rollback field changes
- **THEN** the previous approval cannot be reused and a new complete request is required

### Requirement: The macOS executor is a separate security domain
The system SHALL execute approved macOS actions only in a non-agent host process separate from the Agent Server and autonomous Coding environment. Executor control authority, writable state, confirmation state, signing keys, host credentials, Keychain access, private keys, and secret environment values SHALL NOT be exposed through Docker mounts, environment variables, graph state, checkpoints, messages, tool arguments, logs, or repository files. A direct request from autonomous Coding SHALL NOT cause host execution without contemporaneous human confirmation of the exact digest.

#### Scenario: Autonomous environment probes for host authority
- **WHEN** autonomous Coding inspects mounts, process metadata, network services, graph state, repository files, or environment variables
- **THEN** it cannot recover executor authority, forge a host receipt, bypass host confirmation, or execute a Mac-host action

#### Scenario: Direct executor request
- **WHEN** an unapproved, forged, or replayed client calls the host executor
- **THEN** no host command runs without valid pending request state, a single-use digest, and matching human confirmation

### Requirement: Host actions use a narrow policy catalog
The host executor SHALL support only reviewed action categories needed for read-only host inspection, bounded HTTPS download and verification, package-manager invocation, application installation or staging, and native application invocation. Each category SHALL enforce its own executable, argv, path, privilege, timeout, and output policy. The executor SHALL reject general terminal access, arbitrary shell or interpreter execution, background persistence, launch agents, login items, kernel or security-policy changes, credential access, GitHub publication, authenticated remote Git operations, SSH, and Docker control.

#### Scenario: Read-only Mac inspection
- **WHEN** the human approves an inspection action for exact safe host commands such as macOS version, architecture, disk space, application presence, or application version
- **THEN** the executor returns only the bounded requested facts without exposing unrelated host state

#### Scenario: Approved package or application operation
- **WHEN** the human approves an allowed Homebrew, download, DMG, application staging, or native application action with all required fields
- **THEN** the executor runs only the category-specific fixed argv operation and verifies the declared outcome

#### Scenario: Prohibited host capability
- **WHEN** a request attempts privilege escalation, credential access, persistence, arbitrary scripting, GitHub publication, remote push, SSH, Docker control, or an unrecognized executable
- **THEN** the executor rejects it regardless of model instruction

### Requirement: Privilege and user interaction remain human-controlled
The host executor SHALL run without automatic privilege escalation and SHALL NOT collect or transmit passwords, biometric data, Keychain secrets, or authentication responses. If macOS requires native authorization, GUI installation, license acceptance, Gatekeeper approval, or another user-controlled interaction, the system SHALL pause and clearly identify the exact remaining human action.

#### Scenario: Operation requires administrator authorization
- **WHEN** an approved operation requires `sudo`, an administrator password, Touch ID, or a privileged installer decision
- **THEN** the executor does not automate or capture that authorization and reports the required user-controlled step

#### Scenario: DMG or application requires GUI interaction
- **WHEN** installation cannot safely complete through the approved non-interactive action
- **THEN** the executor stages and verifies the artifact, then stops with precise manual instructions rather than simulating consent

### Requirement: Host actions are single-use, durable, and bounded
The system SHALL persist non-secret request status across UI, Agent Server, and executor restarts. Each digest SHALL be single-use, concurrent execution SHALL be locked, retries SHALL return the existing terminal result, foreground execution SHALL have a reviewed timeout, and cancellation SHALL terminate only the process tree created by that request.

#### Scenario: Duplicate approval or resume
- **WHEN** the same request is approved, resumed, retried, or delivered more than once
- **THEN** at most one host operation executes and every caller receives the same terminal result

#### Scenario: Executor restarts during execution
- **WHEN** the host executor restarts while an operation is pending or running
- **THEN** it recovers a safe durable state, does not silently repeat a mutation, and reports whether human inspection or a new request is required

#### Scenario: Operation times out or is cancelled
- **WHEN** the reviewed timeout expires or the human cancels a running action
- **THEN** the executor stops the request-owned process tree, records known mutations, and does not terminate unrelated host processes

### Requirement: Every host operation produces a redacted receipt
The system SHALL return a verifiable non-secret receipt containing the request digest, terminal status, timestamps, action category, executable and argv summary, canonical working directory, approved and observed paths, artifact hashes, exit status, bounded output summary, verified outcome, mutations, rollback result, and any remaining human step. Receipts and logs SHALL exclude secret environment values, passwords, tokens, Keychain data, private keys, authorization prompts, unrelated files, and unbounded command output.

#### Scenario: Successful host operation
- **WHEN** an approved operation completes and its declared outcome is verified
- **THEN** Coder and the human receive a durable receipt that distinguishes Mac-host effects from container effects

#### Scenario: Failed or partial host operation
- **WHEN** execution fails, times out, is cancelled, or leaves a partial mutation
- **THEN** the receipt reports the exact known state and rollback result without claiming success or complete recovery

### Requirement: Jasper and Coding preserve the host boundary in follow-up work
Jasper and Coding SHALL use host-operation receipts as the source of truth for macOS state. They SHALL NOT infer successful installation from an approved request alone, treat a staged artifact as an installed application, or repeat a failed host operation autonomously.

#### Scenario: Approval exists but execution did not succeed
- **WHEN** a request was approved but its receipt is failed, cancelled, expired, partial, or absent
- **THEN** Jasper and Coding report that macOS state is unverified and do not claim installation

#### Scenario: Verified receipt returns to Coding
- **WHEN** the receipt verifies the requested host outcome
- **THEN** autonomous Coding may continue repository-local follow-up work using that verified result without acquiring host execution authority
