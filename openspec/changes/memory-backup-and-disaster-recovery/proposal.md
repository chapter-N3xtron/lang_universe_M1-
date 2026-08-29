# Memory backup and disaster recovery research

## Why

Seven-day item recovery in phase 5 protects an owner from a recent exact-item deletion; it is not disaster recovery. A separate architecture decision is required for database loss, host loss, corruption, and operator restore. The previously proposed custom encryption, scheduling, WebDAV, credential-broker, and backup UI design was rejected. This change records research and required spikes without authorizing runtime implementation.

## What Changes

- Establish an architecture/research gate for an established browser-manageable backup product using Hetzner Storage Share (managed Nextcloud) through WebDAV.
- Compare Duplicati, Kopia, and Backrest/restic. Duplicati is the leading candidate because its documented product surface combines WebDAV, browser management, client-side encryption, scheduling, retention, and restore, but it is not selected.
- Require a synthetic spike and explicit human approval of product, backup boundary, credential mechanism, and restore scope before any implementation.
- Separate phase 5's exact seven-day item recovery from disaster-recovery backups and cap backup persistence of deleted source data at 30 days with no legal hold.
- Record Agent Server/PostgreSQL authority boundaries and prohibit unsupported claims of an atomic memory-only backup.
- Preserve architecture compatibility, not implementation, for a possible future remote primary database.

## Capabilities

### New Capabilities

- `memory-backup-and-disaster-recovery`: Research, product-selection, consistency, secrets, retention, restore, and drill requirements for future backup architecture. Requirements in this change gate selection and future authorization; they do not authorize runtime code or deployment.

### Modified Capabilities

- None.

## Impact

Documentation only. No runtime, deployment, UI, database, secret-store, scheduling, encryption, WebDAV, or remote-primary implementation is authorized. A later human-approved implementation change is required after the spike resolves the blocking decisions.
