# Phase_10_Focused_verification

## Why

Phases 1–9 change several architecture authority and trust boundaries, but passing source-level tests alone cannot prove that the graph, persistence, tenant isolation, MCP, and streaming behavior work at the intended runtime layer. A narrow, deterministic verification contract is needed so each claim is backed by correctly classified evidence without expanding into unrelated suites or deployed final acceptance.

## What Changes

- Define a focused verification matrix for authoritative graph identity, separate registration and authentication, genuine subgraph inheritance and interrupts, Agent Server PostgreSQL authority, memory/RAG tenant boundaries, typed Coder reports and Jasper summaries, MCP backend parity and security, stream disconnect/rejoin, and removal of obsolete references.
- Separate evidence into unit/mocked, graph/integration, container, and deployed classes, and prohibit presenting source or mocked test results as container or deployed validation.
- Require deterministic positive and negative checks at the lowest layer capable of proving each claim, with tenant, authorization, persistence, resume, and obsolete-reference failure cases kept explicit.
- Require strict OpenSpec validation plus lint and type checks limited to files changed while implementing this verification capability, where applicable.
- Keep verification narrow: no real-browser speech-to-text or text-to-speech checks and no broad unrelated backend or frontend suites.
- Reserve deployed final acceptance for the subsequent deployed-acceptance phase; this change defines how deployed evidence is identified and reported but does not perform or approve that acceptance.
- Provide planning artifacts only; this proposal does not implement tests, alter runtime code, or execute deployed validation.

## Capabilities

### New Capabilities

- `focused-architecture-verification`: Deterministic, layer-classified verification and evidence requirements for the architecture delivered by phases 1–9.

### Modified Capabilities

- None.

## Impact

This change adds planning artifacts under `openspec/changes/phase-10-focused-verification/`. Later implementation may add or refine narrowly targeted test fixtures, graph/integration checks, container probes, evidence manifests, and changed-file validation commands around the phase 1–9 surfaces. It does not authorize application implementation, broad regression suites, browser audio validation, production changes, or deployed final acceptance.
