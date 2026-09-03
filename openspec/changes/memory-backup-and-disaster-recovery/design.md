## Context

This is an architecture/research record only. The human rejected a custom keychain/encryption/scheduling/WebDAV broker. No product has been selected and no runtime work is authorized.

Phase 5 item recovery and disaster recovery are different controls:

- **Item recovery:** an exact deleted memory is excluded immediately, restorable only by its owner for exactly seven days, then permanently purged.
- **Disaster recovery:** versioned encrypted backups recover from database/host loss or corruption. Deleted source data may survive in backup versions for at most 30 days; no legal hold applies.

## Observed research and official sources

### Destination and products

- The designated Hetzner Storage Share host is `host105984.frontdesk.de`. Hetzner describes Storage Share as managed Nextcloud, and Nextcloud officially documents WebDAV access. The exact account-specific WebDAV path and application password remain backup-product configuration, not application or agent configuration. Sources: https://www.hetzner.com/storage/storage-share/ and https://docs.nextcloud.com/server/latest/user_manual/en/files/access_webdav.html
- Duplicati officially documents a browser-based UI, scheduled backups, retention, encryption, restore, and WebDAV support. Its combination makes it the leading candidate, not the selected product. Sources: https://docs.duplicati.com/getting-started/set-up-a-backup-in-the-ui , https://docs.duplicati.com/backup-destinations/standard-based-destinations/webdav-destination , https://docs.duplicati.com/configuration-and-management/retention-settings , and https://docs.duplicati.com/getting-started/restoring-files
- Kopia officially supports WebDAV storage and client-side encryption. Its browser/server mode exists, but repository creation and server/UI deployment require a more involved setup to validate. Sources: https://kopia.io/docs/repositories/ , https://kopia.io/docs/repositories/#webdav , https://kopia.io/docs/features/ , and https://kopia.io/docs/reference/command-line/common/server-start/
- Backrest is a web UI/orchestrator for restic. Restic's backend list does not natively include WebDAV; official restic documentation uses rclone for additional services, adding rclone remote configuration and associated secret/config layers. Sources: https://garethgeorge.github.io/backrest/ , https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html , https://restic.readthedocs.io/en/stable/040_backup.html#rclone , and https://rclone.org/webdav/

These are documentation observations, not synthetic proof. Product versions, actual secret exposure, WebDAV interoperability, deployment/UI fit, retention behavior, and restores remain spike questions.

### LangGraph Agent Server and PostgreSQL boundary

- LangGraph Agent Server owns persistence for resources, checkpoints, and Store. Application code must use public APIs and must never select from or write its internal tables. Source: https://docs.langchain.com/langgraph-platform/architecture
- LangChain's self-hosted disaster-recovery guidance makes the operator responsible for backups and recommends managed PostgreSQL backup and point-in-time-recovery capabilities. Source: https://docs.langchain.com/langsmith/disaster-recovery
- PostgreSQL officially supports consistent whole-database logical backup and restore with `pg_dump`/`pg_restore`; `pg_dump` makes a consistent export even with concurrent use. This is PostgreSQL support, not an explicit LangChain product qualification for Agent Server. Sources: https://www.postgresql.org/docs/current/app-pgdump.html and https://www.postgresql.org/docs/current/app-pgrestore.html
- Public Store APIs can enumerate/read authorized records and therefore may support a bounded application memory export. Public documentation does not establish an atomic Store snapshot, an atomic memory-only backup, or a full checkpoint backup through Store APIs. Sources: https://docs.langchain.com/oss/python/langgraph/persistence and https://reference.langchain.com/python/langgraph/store/

Consequently, the spike must prove a consistent source boundary. It must not infer a memory-only atomic snapshot. Whole-database backup is plausible and officially supported by PostgreSQL, but remains unqualified by LangChain until the boundary is approved.

## Goals / Non-Goals

**Goals:**

- Select, through evidence and human approval, an established browser-manageable product.
- Prove WebDAV, encryption, scheduling, retention, consistency, secret handling, restore, drills, and compatibility using synthetic data.
- Define a future architecture that can use Hetzner Storage Share and can remain compatible with a future remote primary database.

**Non-Goals:**

- No runtime/deployment implementation, custom backup format, custom cryptography, custom credential broker, custom scheduler, or custom WebDAV client.
- No direct application access to Agent Server internal PostgreSQL tables.
- No claim of atomic memory-only or checkpoint backup through public Store APIs.
- No remote-primary migration, replication, or operation.

## Candidate assessment

| Candidate | Observed strengths | Spike concerns |
|---|---|---|
| Duplicati | Native WebDAV; browser UI; client-side encryption; scheduling; retention; restore | Prove DB-consistent source acquisition, secret behavior, pruning/deleted-data ceiling, manual encrypted transfer workflow, and deployment fit |
| Kopia | Native WebDAV; encryption; mature snapshot concepts | Prove browser server/repository setup, secret handling, schedule/retention UX, restore granularity, and integration complexity |
| Backrest/restic | Established restic engine with browser orchestration | WebDAV requires rclone; prove extra configuration/secret layers, scheduling ownership, retention, and operational fit |

Duplicati leads only on documented fit. Selection remains blocked pending the comparative synthetic spike.

## Proposed architecture constraints

1. The future product must be established and browser-manageable.
2. The destination must be the Nextcloud WebDAV interface of the designated Hetzner Storage Share host, `host105984.frontdesk.de`.
3. Backups must be encrypted client-side by the selected product using its documented mechanism; the application must not invent cryptography or a backup format.
4. The owner chooses daily or weekly operation. Daily retains seven daily versions; weekly retains four weekly versions.
5. Deleted source data must disappear from all retained backups within 30 days. There is no legal hold.
6. Manual encrypted backup download and upload/restore must be included if the selected established product officially supports that workflow; unsupported granularity must be stated, not emulated with custom code.
7. WebDAV and encryption credentials must use the selected product's documented secret mechanism and never be available to agents, agent tools, contexts, results, errors, or logs. No custom credential-store broker is permitted.
8. Restore drills are mandatory. Restore requires stopped/drained application writes and a documented rollback path.
9. Backup and restore must use a tested compatibility matrix covering Agent Server, PostgreSQL, backup product/format, and required PostgreSQL extensions. Incompatible restore must fail closed.
10. The source is either a consistent whole Agent Server PostgreSQL database backup or a specifically documented supported memory export. Public Store APIs alone do not prove atomicity or checkpoint coverage.
11. Future remote-primary database support is architecture compatibility only. This change adds no remote database, credentials, replication, or migration.
12. The backup scope covers all current live persistent application data: Agent Server PostgreSQL and Redis; Plane PostgreSQL, Redis, MinIO object storage, and RabbitMQ; Temporal PostgreSQL; and `data/ocr/uploads/`. Dependency caches and generated front-end assets are excluded.

## Restore boundary

A whole-database restore can preserve Agent Server-owned resources/checkpoints/Store together but carries broader blast radius and version requirements. A public-API memory export could provide bounded item portability, but only if an official supported export contract or spike-approved consistency protocol exists; it must not be described as atomic and cannot be presented as checkpoint DR. Human approval must choose the boundary and restore scope.

## Security and operating model

The selected backup product, not agents or custom application broker code, owns scheduling, encryption, WebDAV transport, retention, and its documented secret mechanism. Browser management must have explicit authentication and constrained network exposure. Logs, health status, and errors must be tested for secret leakage. Restore operators stop or drain writes before restore, validate versions/extensions and backup integrity, restore into an isolated target when possible, then verify before cutover.

## Unresolved decisions and implementation block

The following are unresolved and implementation-blocking:

- **Product:** Duplicati, Kopia, or Backrest/restic; Duplicati is only the leading candidate.
- **Backup boundary:** whole Agent Server PostgreSQL database or a documented supported bounded memory export.
- **Credential mechanism:** the selected product's exact documented mechanism and acceptable unattended/restore behavior.
- **Restore scope:** whole database versus any supported item/export granularity, including manual encrypted download/upload behavior.
- Browser authentication/network placement, consistency procedure, compatibility matrix, drill cadence/owner, monitoring, and remote-primary adaptation also require evidence.

No implementation may begin until the synthetic spike is complete and a human explicitly approves the product, backup boundary, credential mechanism, and restore scope. Approval must be followed by a separate implementation OpenSpec.
