## Purpose

Define research and human-approval gates for future encrypted disaster recovery without authorizing runtime implementation or confusing backup retention with phase 5 item recovery.

## ADDED Requirements

### Requirement: Architecture remains research-only until explicit approval
The change SHALL NOT authorize runtime, deployment, UI, database, scheduling, encryption, WebDAV, secret-store, or restore implementation. A synthetic comparative spike SHALL precede selection. Implementation SHALL remain blocked until a human explicitly approves the product, backup boundary, credential mechanism, and restore scope, after which a separate implementation OpenSpec is required.

#### Scenario: Leading candidate is documented
- **WHEN** Duplicati is identified as the leading candidate
- **THEN** it remains unselected and no runtime implementation is authorized

#### Scenario: Any blocking decision is unresolved
- **WHEN** product, backup boundary, credential mechanism, or restore scope lacks explicit human approval
- **THEN** implementation stops

### Requirement: An established browser-manageable product owns backup functions
The selected architecture SHALL use an established browser-manageable backup product. The product SHALL own backup formatting, client-side encryption, scheduling, retention, WebDAV transport, and restore using documented product capabilities. The application MUST NOT implement custom cryptography, a custom backup format, a custom scheduler, a custom WebDAV client, or a custom credential broker.

#### Scenario: Custom component is proposed
- **WHEN** an architecture requires application-built cryptography, backup formatting, scheduling, WebDAV transport, or credential brokering
- **THEN** the architecture is rejected

### Requirement: Candidate selection is evidence-based
The synthetic spike SHALL compare Duplicati, Kopia, and Backrest/restic for source consistency, secret behavior, Nextcloud WebDAV behavior, restore granularity, deployment, browser UI integration, retention, and operational complexity. Duplicati MAY be treated as the leading candidate but SHALL NOT be selected without spike evidence and human approval.

#### Scenario: Candidate comparison completes
- **WHEN** all three candidates have been tested with synthetic data
- **THEN** the decision record reports comparable results, limitations, exact versions, and unresolved risks before requesting human selection

### Requirement: Destination and encryption are constrained
The future architecture SHALL target Hetzner Storage Share as managed Nextcloud through its WebDAV interface. Backup payloads SHALL be client-side encrypted by the selected product. WebDAV and encryption credentials SHALL be held only through that product's documented secret mechanism and MUST NOT be available to agents, agent tools, contexts, results, errors, or logs.

#### Scenario: Agent requests a backup credential
- **WHEN** an agent or agent-visible capability requests a WebDAV password, encryption key, repository password, or equivalent secret
- **THEN** access is denied and no secret value is exposed

### Requirement: Schedule and retention follow owner policy
The owner SHALL be able to choose daily or weekly backups. Daily mode SHALL retain seven daily versions; weekly mode SHALL retain four weekly versions. Deleted source data MUST be removed from all backup versions within 30 days, and no legal hold applies.

#### Scenario: Owner selects weekly mode
- **WHEN** weekly backup mode is active
- **THEN** the established product schedules weekly operation and retains at most four successful weekly policy versions after pruning

#### Scenario: Source data was deleted
- **WHEN** an item is deleted from the source
- **THEN** no retained backup may continue to contain it beyond 30 days

### Requirement: Item recovery and disaster recovery remain separate
The architecture SHALL distinguish phase 5 exact-item recovery from disaster recovery. Phase 5 deletion SHALL exclude an item immediately, allow exact-owner restore for exactly seven days, and then permanently purge it. Backup restore SHALL NOT extend or be represented as that item-recovery window.

#### Scenario: Seven-day item window ends
- **WHEN** the phase 5 item-recovery window expires
- **THEN** the item is not restorable through the phase 5 item API even if a disaster-recovery backup remains within its separate retention ceiling

### Requirement: Source consistency must be proved without internal-table access
The spike SHALL prove consistency using either a whole Agent Server PostgreSQL database backup or a specifically documented supported bounded memory export. Application code MUST NOT select or write Agent Server internal tables. Public Store APIs MUST NOT be claimed to provide an atomic memory-only snapshot or a full checkpoint backup absent official documentation and proof.

#### Scenario: Public Store enumeration is proposed as backup
- **WHEN** public Store APIs enumerate bounded authorized memory records
- **THEN** the result may be evaluated as a bounded export but is not labeled atomic and is not labeled a checkpoint or full Agent Server backup

#### Scenario: Whole-database logical backup is used
- **WHEN** `pg_dump`/`pg_restore` supplies the consistent source and restore path
- **THEN** the design records that PostgreSQL officially supports the tools but LangChain has not explicitly product-qualified that path for Agent Server

### Requirement: Restore is controlled and compatibility-tested
Restore SHALL occur only with application writes stopped or drained. The selected process SHALL verify backup integrity and an explicit compatibility matrix for Agent Server, PostgreSQL, backup-product/format, and required extension versions. Restore drills SHALL use synthetic or isolated targets and SHALL document verification, failure handling, and rollback.

#### Scenario: Writes remain active
- **WHEN** an operator attempts restore while application writes are not stopped or drained
- **THEN** restore is blocked

#### Scenario: Version or extension is incompatible
- **WHEN** the compatibility matrix does not approve the restore target
- **THEN** restore fails closed before production cutover

### Requirement: Restore scope is explicit
The selected architecture SHALL state whether restore is whole database, documented bounded memory export, or another officially supported product granularity. Manual encrypted backup download and upload/restore SHALL be supported when the selected established product documents that workflow. Unsupported item-level or partial restore MUST NOT be emulated through custom backup parsing or direct internal-table writes.

#### Scenario: Product supports manual encrypted transfer
- **WHEN** the selected product officially supports downloading encrypted backup material and uploading it for restore
- **THEN** the approved restore design includes and drills that workflow

#### Scenario: Requested granularity is unsupported
- **WHEN** an operator requests unsupported item-level or partial restore
- **THEN** the system reports it unsupported rather than parsing a custom format or modifying internal tables

### Requirement: Future remote primary is compatibility-only
The architecture SHALL document compatibility considerations for a future remote primary database but MUST NOT implement remote-primary provisioning, credentials, migration, replication, failover, or operation under this change.

#### Scenario: Remote primary is requested
- **WHEN** implementation of a remote primary database is requested under this change
- **THEN** the request is rejected as outside the research-only scope
