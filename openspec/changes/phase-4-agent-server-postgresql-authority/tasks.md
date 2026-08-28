## 1. Authority Inventory and Test Baseline

- [x] 1.1 Inventory every deployed Jasper, standalone Coder, nested Coder, startup, and bridge path that constructs a checkpointer/Store or calls the legacy Coder persistence manager, and classify each current read/write/recovery authority.
- [x] 1.2 Add focused graph-construction tests that fail when top-level Jasper or standalone Coder attaches an application-owned concrete saver or Store.
- [x] 1.3 Add focused authority tests covering PostgreSQL-versus-legacy disagreement, legacy-only state, missing/corrupt authoritative state, and authoritative commit failure without fallback.

## 2. Agent Server Persistence Ownership

- [x] 2.1 Refactor top-level Jasper graph construction to compile without an application-supplied concrete checkpointer or concrete Store and verify deployed Agent Server runtime injection.
- [x] 2.2 Refactor standalone Coder graph construction to compile without an application-supplied concrete checkpointer or concrete Store and verify deployed Agent Server runtime injection.
- [x] 2.3 Configure Coder's Jasper-nested form to inherit the parent checkpointer and thread identity through runtime-managed nested checkpoint lineage, with no second saver or derived Coder thread.
- [x] 2.4 Verify Store remains separately runtime-configured for approved long-term cross-thread access and cannot reconstruct or advance a conversation checkpoint.

## 3. Runtime Identity, Progression, and Concurrency

- [x] 3.1 Enforce Agent Server `thread_id` as the durable Jasper/standalone-Coder identity and propagate it unchanged into nested Coder while keeping run, attempt, Temporal, correlation, and Redis identifiers as non-authoritative metadata.
- [x] 3.2 Add fail-closed validation and bounded diagnostics for conflicting, ambiguous, or missing thread identity mappings without logging checkpoint payloads or secrets.
- [x] 3.3 Route same-thread mutations through Agent Server concurrency controls so contenders serialize or receive an explicit busy/conflict result, and verify distinct threads remain independently executable.
- [x] 3.4 Ensure terminal and resumable progress is acknowledged only after the required PostgreSQL checkpoint commit and that retries derive their next inner action solely from the accepted checkpoint lineage.

## 4. Retire Competing Production Authorities

- [x] 4.1 Remove production initialization and read, write, dual-write, recovery, and compare/select calls to the orphaned Coder SQLite/PostgreSQL persistence manager.
- [x] 4.2 Keep the legacy manager implementation, configuration definitions, schemas, and persisted data physically intact and mark them inert pending Phase 9 cleanup.
- [x] 4.3 Restrict Redis integration to ephemeral signaling, coordination, and disposable delivery state, removing any checkpoint recovery or cursor arbitration dependency.
- [x] 4.4 Update the Phase-2 Temporal bridge so it owns only outer scheduling, retries, timeout policy, and correlation; retries must preserve the Agent Server thread identity and must not persist or direct an inner cursor.

## 5. Focused Verification and Cutover

- [x] 5.1 Verify Jasper and standalone Coder recover from the latest committed PostgreSQL checkpoint after worker/process restart and do not claim work completed after the last commit.
- [x] 5.2 Verify nested Coder interrupt/restart recovery uses the parent thread's inherited checkpoint lineage and never consults a Coder-owned manager.
- [x] 5.3 Verify same-thread overlap yields one ordered lineage, PostgreSQL failure cannot report durable success, and identity conflicts fail without auxiliary fallback.
- [x] 5.4 Verify Redis loss affects only ephemeral signals and a Temporal retry resumes or conflicts according to Agent Server state even when Temporal history appears ahead.
- [x] 5.5 Record focused cutover and rollback evidence confirming Agent Server PostgreSQL is the sole production checkpoint authority, Store remains separate, legacy assets were not deleted, and no broad deployment acceptance is claimed.
