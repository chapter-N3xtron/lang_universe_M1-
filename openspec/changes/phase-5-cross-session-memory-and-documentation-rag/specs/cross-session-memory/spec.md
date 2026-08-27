## Purpose

Define permissioned, durable memory that can be recalled across sessions without confusing checkpoint state with memory or crossing personal and work security boundaries.

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

### Requirement: Personal and work memory are separate security tenants
The system SHALL place personal and work contexts in different tenant scopes and MUST NOT search, read, write, copy, merge, summarize, or delete memory across those tenant boundaries in one operation. A work-context operation additionally SHALL require current work-tenant membership and an operation-specific grant for the target owner scope.

#### Scenario: Personal session recalls memory
- **WHEN** an authorized request originates in a personal context
- **THEN** the system searches only the verified principal's personal tenant and owner scope

#### Scenario: Work session recalls memory
- **WHEN** a verified work member has `read` permission for the target work owner scope
- **THEN** the system searches only that work tenant, trust domain, and permitted owner scope

#### Scenario: Cross-context recall is requested
- **WHEN** a personal request targets work memory or a work request targets personal memory
- **THEN** the system denies the request rather than combining results

#### Scenario: Work membership is revoked
- **WHEN** a principal no longer has current membership or the required grant in a work tenant
- **THEN** subsequent memory operations in that tenant are denied

### Requirement: Memory access follows least-privilege operation rules
The system SHALL enforce separate `read`, `write`, and `delete` permissions. A personal owner can operate only on that owner's personal records; a work principal can operate only on owner scopes and operations granted by work policy; a delegated agent can act only within the verified user's current context and granted operation; infrastructure operators have no default content access. No principal or agent SHALL enumerate tenants, trust domains, or owners outside its authorized scope.

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
Each memory record SHALL have an immutable record identifier, schema version, tenant, trust domain, owner, memory kind, bounded content, bounded metadata, provenance, creation time, update time, retention class or expiry, and lifecycle state. Provenance SHALL identify the source session or approved external source, creating principal or service, creation method, and source time when known. Configured hard limits SHALL bound record bytes, metadata fields and bytes, batch size, query length, and returned result count; over-limit writes SHALL fail rather than truncate silently.

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
The system SHALL create or update cross-session memory only through an authorized memory write. It MUST NOT treat checkpoint state, thread history, messages, tool state, or session persistence as cross-session memory merely because those records are durable, and it MUST NOT automatically promote checkpoint contents into memory.

#### Scenario: Session checkpoint is saved
- **WHEN** Agent Server persists a checkpoint or thread state
- **THEN** no cross-session memory record is created unless a separate authorized memory write succeeds

#### Scenario: Memory references a session
- **WHEN** an authorized memory record is derived from a session
- **THEN** provenance may reference that session without copying checkpoint execution state into the memory layer

### Requirement: Initial memory retrieval makes no semantic-search claim
The initial system SHALL support only exact-key lookup, authorized metadata filtering, and bounded lexical matching for memory retrieval. Responses SHALL identify the match mode used and MUST NOT label lexical or metadata results as vector, embedding, conceptual, ontology-based, or semantic search.

#### Scenario: Lexical recall succeeds
- **WHEN** an authorized caller submits a bounded lexical query
- **THEN** the system returns scoped matches with `lexical` as the match mode and provenance for each result

#### Scenario: Semantic retrieval is requested before support exists
- **WHEN** a caller requests vector or semantic memory retrieval
- **THEN** the system returns an unsupported-capability response rather than presenting lexical results as semantic

### Requirement: Retention and deletion are enforceable
The system SHALL associate every memory record with an approved retention policy or explicit expiry. Expired or deleted records SHALL be excluded from normal reads immediately. An authorized delete SHALL be scoped to an exact verified tenant, trust domain, owner, and record identifier; it SHALL be idempotent, produce a non-content audit event, and progress to physical purge according to the approved deletion policy. Restore SHALL be denied unless a separately approved policy explicitly permits it.

#### Scenario: Record expires
- **WHEN** a record passes its approved expiry
- **THEN** the system no longer returns it and schedules or performs purge according to policy

#### Scenario: Owner deletes a personal record
- **WHEN** the verified personal owner with `delete` permission requests deletion by exact record identifier
- **THEN** the system makes the record unavailable, records a sanitized deletion event, and applies the approved purge policy

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
The system SHALL emit bounded audit events for allowed and denied memory operations containing time, verified principal or service identifier, tenant, trust domain, owner scope, operation, policy decision, reason class, correlation identifier, and affected record count. Audit events MUST NOT duplicate memory content, credentials, or internal reasoning and SHALL follow an approved audit-retention and access policy.

#### Scenario: Access is denied
- **WHEN** a memory request fails authorization
- **THEN** the system records a sanitized denial event without recording the requested memory content

#### Scenario: Authorized query completes
- **WHEN** a memory query succeeds
- **THEN** the system records its scope, match mode, and bounded result count without copying result bodies into the audit event
