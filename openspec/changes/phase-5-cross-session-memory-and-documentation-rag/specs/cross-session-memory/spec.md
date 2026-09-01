## Purpose

Define permissioned private durable memory for one person per installation without confusing checkpoint state with memory. Multiple installations are supported through separate installation databases; shared/work memory is not part of this phase.

## ADDED Requirements

### Requirement: Cross-session memory uses an application-owned Store boundary
The system SHALL persist cross-session memory through supported Agent Server Store operations in application-owned namespaces. The system MUST NOT write application memory records directly into Agent Server internal PostgreSQL tables, even when Store and other Agent Server persistence share one PostgreSQL deployment.

#### Scenario: Memory is persisted
- **WHEN** an authorized caller writes a valid cross-session memory record
- **THEN** the system stores it through the Agent Server Store interface in an application-owned memory namespace

#### Scenario: Direct internal-table access is requested
- **WHEN** a component attempts to read or write cross-session memory through an Agent Server internal table
- **THEN** the system rejects the operation and records a sanitized policy violation

### Requirement: Verified identity and explicit authorization are mandatory
The system SHALL authenticate the requesting principal and derive tenant, trust-domain, and owner scope from verified server-side identity before every memory operation. It SHALL authorize the requested operation explicitly, deny missing or conflicting identity attributes, and deny access by default. Caller-supplied namespace or owner values MUST NOT override verified identity.

#### Scenario: Verified owner writes personal memory
- **WHEN** a verified principal requests `write` within that principal's personal tenant, trust domain, and owner scope and policy grants `cross-session-memory:write`
- **THEN** the system permits the bounded write

#### Scenario: Unverified identity attempts access
- **WHEN** identity, tenant, trust-domain, or owner verification is absent or fails
- **THEN** the system denies the operation without disclosing whether a matching record exists

#### Scenario: Caller spoofs an owner
- **WHEN** a caller supplies an owner or namespace that conflicts with verified server-side scope
- **THEN** the system denies the operation and does not access the supplied scope

### Requirement: Memory is private to one person per installation
The system SHALL use a separate installation/database for each person. It SHALL derive a server-generated opaque tenant ID, trust domain `local-installation-v1`, owner type `person`, and owner ID exclusively from trusted server configuration. Browser, prompt, agent, and tool input MUST NOT select these values. Shared and work memory operations are unsupported in this phase.

#### Scenario: Installation owner recalls memory
- **WHEN** the installation owner makes an authorized request
- **THEN** the system searches only that installation's server-derived tenant and owner scope

#### Scenario: Another scope is requested
- **WHEN** a caller requests another tenant, owner, trust domain, shared scope, or work scope
- **THEN** the system denies the request without accessing that scope

### Requirement: Memory access follows least-privilege operation rules
The system SHALL enforce separate `read`, `write`, `delete`, `restore`, and `permanent-delete` permissions. The installation owner can operate only on that owner's private records; a delegated agent can act only within the verified owner's installation scope and granted operation; infrastructure operators have no default content access. No principal or agent SHALL enumerate tenants, trust domains, or owners outside its authorized scope.

#### Scenario: Read permission does not imply write
- **WHEN** a principal with only `cross-session-memory:read` requests a write or delete
- **THEN** the system denies the request

#### Scenario: Delegated agent reads memory
- **WHEN** an agent invocation carries a valid, server-created delegation for `read` in one verified scope
- **THEN** the system returns only authorized bounded results from that scope

#### Scenario: Operator lacks content grant
- **WHEN** an infrastructure operator without an explicit content-access grant requests a memory payload
- **THEN** the system denies content access

### Requirement: Memory records are bounded and provenance-bearing
Each memory record SHALL have an immutable record identifier, schema version, tenant, trust domain, owner, memory kind, bounded content, bounded metadata, provenance, creation time, update time, and lifecycle state. Kinds SHALL be exactly `user preferences`, `user-provided facts`, `project decisions`, `task outcomes`, and `reusable instructions`. Each kind SHALL have a 15 MB total limit. Content SHALL be at most 32 KB; metadata at most 8 KB and 32 fields; a query at most 4 KB; an already-authorized candidate scan at most 1000; results at most 20; a response at most 256 KB; and a write batch at most 10. Over-limit writes SHALL fail without truncation or partial writes. Reaching a kind limit SHALL require an explicit owner decision and MUST NOT cause automatic eviction. Provenance SHALL identify the source session or approved external source, creating principal or service, creation method, and source time when known.

#### Scenario: Valid record is accepted
- **WHEN** an authorized write supplies all required fields within configured limits
- **THEN** the system persists the record with its identity, scope, provenance, retention, and lifecycle metadata

#### Scenario: Oversized record is submitted
- **WHEN** record content, metadata, or batch size exceeds a hard limit
- **THEN** the system rejects the write without creating a partial record

#### Scenario: Result limit is requested
- **WHEN** a caller requests more than the configured maximum result count
- **THEN** the system applies the hard maximum or rejects the request and never performs an unbounded return

### Requirement: Memory creation is explicit and checkpoints are not memory
The system SHALL create or update cross-session memory only through an authorized memory write. It MUST NOT treat checkpoint state, thread history, messages, tool state, session persistence, or a thread's bounded stable-document-ID links as cross-session memory merely because those records are durable, and it MUST NOT automatically promote checkpoint contents or session-document references into memory. The implementation uses ordinary documented Store operations and MUST NOT claim compare-and-swap, multi-key transaction, or conflicting-write safety that the Store does not provide.

#### Scenario: Session checkpoint is saved
- **WHEN** Agent Server persists a checkpoint or thread state
- **THEN** no cross-session memory record is created unless a separate authorized memory write succeeds

#### Scenario: Memory references a session
- **WHEN** an authorized memory record is derived from a session
- **THEN** provenance may reference that session without copying checkpoint execution state into the memory layer

#### Scenario: Thread restores linked document IDs
- **WHEN** a checkpointed thread restores its bounded Session Documents references
- **THEN** those thread-scoped IDs remain execution state and no cross-session memory record or document-content copy is created

### Requirement: Initial memory retrieval makes no semantic-search claim
The initial system SHALL support only exact-key lookup, authorized metadata filtering, and bounded lexical matching for memory retrieval. Responses SHALL identify the match mode used and MUST NOT label lexical or metadata results as vector, embedding, conceptual, ontology-based, or semantic search.

#### Scenario: Lexical recall succeeds
- **WHEN** an authorized caller submits a bounded lexical query
- **THEN** the system returns scoped matches with `lexical` as the match mode and provenance for each result

#### Scenario: Semantic retrieval is requested before support exists
- **WHEN** a caller requests vector or semantic memory retrieval
- **THEN** the system returns an unsupported-capability response rather than presenting lexical results as semantic

### Requirement: Retention and deletion are enforceable
The system SHALL retain active memory without a default TTL until owner deletion; a category limit requires an explicit owner decision and never automatic eviction. Each memory ID SHALL have exactly one current Store item in its server-derived kind namespace, with no revision items, materialized head copy, or memory operation manifest. Delete SHALL overwrite that item as deleted, apply a per-item native Store TTL, and exclude it from all normal reads immediately. Only the exact owner SHALL be able to restore the exact item through the inclusive logical cutoff at `deleted_at + 7 days`; restore SHALL rewrite active state and clear its TTL. After that instant restore SHALL be denied even if asynchronous native sweeping has not physically removed the item. Owner-authorized Permanently Delete SHALL physically delete the exact item immediately. Native sweeping is best-effort, so logical expiry and physical deletion time are distinct. Overlapping writes or lifecycle calls are last-write-wins Store operations without CAS, multi-key transaction, or conflicting-write guarantee; revision and stale-input checks are non-atomic validation only.

#### Scenario: Deleted record passes its logical restore cutoff
- **WHEN** the current time is later than `deleted_at + 7 days`
- **THEN** normal reads exclude the record and restore is denied regardless of whether the native TTL sweeper has physically removed it

#### Scenario: Owner restores at the boundary
- **WHEN** the exact owner restores at or before `deleted_at + 7 days`
- **THEN** the system rewrites the one item as active and clears its TTL

#### Scenario: Owner deletes a personal record
- **WHEN** the verified personal owner with `delete` permission requests deletion by exact record identifier
- **THEN** the system overwrites the one item as deleted, excludes it immediately, records a sanitized deletion event, and applies its per-item TTL

#### Scenario: Owner permanently deletes a personal record
- **WHEN** the verified owner requests permanent deletion of an exact deleted record
- **THEN** the system physically deletes that exact Store item without retaining a memory tombstone

#### Scenario: Delete targets another scope
- **WHEN** a delete request targets a different tenant, trust domain, or owner than the verified authorized scope
- **THEN** the system denies the request without changing any record

### Requirement: Agents never receive persistence credentials
The system SHALL keep database, Agent Server Store, and other persistence credentials in trusted server infrastructure. Agents SHALL receive only capability-scoped operations and bounded results, and memory payloads, errors, or telemetry MUST NOT expose credentials or secret connection material.

#### Scenario: Agent invokes memory capability
- **WHEN** an authorized agent requests a memory operation
- **THEN** trusted server code performs the operation without placing persistence credentials in agent context

#### Scenario: Error occurs
- **WHEN** a memory operation fails
- **THEN** the returned error and audit telemetry contain sanitized identifiers and failure classes but no credential or connection-secret values

### Requirement: Access decisions are auditable without duplicating content
The system SHALL emit bounded audit events for allowed and denied memory operations containing time, verified principal or service identifier, tenant, trust domain, owner scope, operation, policy decision, reason class, correlation identifier, and affected record count. Audit events MUST NOT duplicate memory content, queries, credentials, or internal reasoning. They SHALL carry a per-item native Store TTL, remain logically readable through the exact 90-day boundary, be excluded immediately after that boundary while awaiting best-effort physical sweeping, and be accessible only to the installation owner. No application audit sweeper SHALL be added.

#### Scenario: Access is denied
- **WHEN** a memory request fails authorization
- **THEN** the system records a sanitized denial event without recording the requested memory content

#### Scenario: Authorized query completes
- **WHEN** a memory query succeeds
- **THEN** the system records its scope, match mode, and bounded result count without copying result bodies into the audit event
count without copying result bodies into the audit event
