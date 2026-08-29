## 1. Research record

- [x] 1.1 Record official-source observations for Hetzner Storage Share/Nextcloud WebDAV, Duplicati, Kopia, Backrest/restic/rclone, LangGraph Agent Server persistence boundaries, LangChain self-hosted DR guidance, and PostgreSQL logical backup support.
- [x] 1.2 Record Duplicati as the leading candidate, not a selection, and separate seven-day phase 5 item recovery from disaster recovery.

## 2. Synthetic comparative spike (no product-data or runtime rollout)

- [ ] 2.1 Build disposable synthetic deployments of Duplicati, Kopia, and Backrest/restic with an isolated Hetzner-compatible Nextcloud WebDAV test destination; record exact versions and configuration layers.
- [ ] 2.2 Prove each candidate's source-data consistency using either a stopped/drained whole-database `pg_dump`/`pg_restore` path or a documented supported bounded memory-export path. Do not claim an atomic memory-only snapshot.
- [ ] 2.3 Compare documented encryption, key/password generation and recovery, redaction, process/environment/file/UI exposure, rotation, unattended use, and the product's secret mechanism. Prove agents cannot receive secrets.
- [ ] 2.4 Test WebDAV create/list/upload/download/delete, interrupted transfer, retry, destination corruption, TLS/certificate failure, authentication failure, and retention pruning.
- [ ] 2.5 Test owner choice of daily or weekly schedules, retention of seven daily or four weekly versions, and removal of deleted source data from all backup versions within 30 days with no legal hold.
- [ ] 2.6 Compare restore granularity: whole database, bounded memory export if documented, and manual encrypted download/upload restore if the candidate officially supports it. Record what cannot be restored independently.
- [ ] 2.7 Compare browser deployment and UI integration, authentication, bind/network exposure, upgrades, health reporting, schedule management, and operational complexity.
- [ ] 2.8 Run synthetic backup/restore drills with stopped/drained application writes and verify content, metadata, owner scope, deletion state, audit behavior, and failure rollback.
- [ ] 2.9 Test selected Agent Server, PostgreSQL, backup-product, backup-format, and required extension versions across backup and restore; define the compatibility matrix and upgrade order.
- [ ] 2.10 Document how each architecture remains compatible with a future remote primary database without implementing migration, replication, or remote-primary credentials.

## 3. Human decision gates

- [ ] 3.1 Present evidence and trade-offs for Duplicati, Kopia, and Backrest/restic; obtain explicit human product selection. Duplicati's leading-candidate status is insufficient.
- [ ] 3.2 Obtain explicit human approval of the backup boundary: whole Agent Server PostgreSQL database or a specifically documented supported export. Stop if source consistency is unproved.
- [ ] 3.3 Obtain explicit human approval of the selected product's credential mechanism and prove credentials are unavailable to agents.
- [ ] 3.4 Obtain explicit human approval of restore scope and granularity, including whether manual encrypted download/upload is supported and required.
- [ ] 3.5 Create a separate implementation OpenSpec only after 3.1–3.4 are approved; this research change must not be treated as runtime authorization.

## 4. Validation

- [ ] 4.1 Run project-local strict OpenSpec validation and resolve errors.
- [ ] 4.2 Run `git diff --check` and confirm only OpenSpec documents changed.
