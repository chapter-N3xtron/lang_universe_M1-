# Phase 5 PostgreSQL least-privilege preparation

This directory contains preparation artifacts only. Nothing here is invoked by
Docker Compose, image build, application startup, or tests.

## Boundary

The deployment needs two trusted PostgreSQL service identities:

- `agent_server_role`: the standalone Agent Server connection used by the
  documented `DATABASE_URI` boundary. It owns only the observed Agent Server
  relations and the `public` schema so startup migrations can create, alter,
  index, and use server persistence objects.
- `session_catalog_role`: the application projection connection used by the
  repository's `POSTGRES_URI` boundary. It owns only `session_catalog`, whose
  existing `ensure_catalog_schema()` performs idempotent DDL as well as runtime
  reads and writes.

Both roles are login roles because the two connection pools authenticate
independently. They are explicitly non-superuser, cannot create roles or
databases, cannot replicate, and cannot bypass row security. No browser, owner,
Jasper, Coder, Librarian, or OCR identity is a PostgreSQL role. Those identities
reach persistence only through Agent Server HTTP/auth hooks and trusted
capability code. A model-visible identity must never receive either URI.

Phase 5 memory and documentation records both use the one Agent Server
`BaseStore`, which is physically the `public.store` relation in the observed
deployment. The supported Store API carries namespaces, not separate database
connections or PostgreSQL principals. Therefore PostgreSQL grants cannot make
memory rows and documentation rows mutually inaccessible behind that one
service connection. Isolation remains default-deny capability authorization,
server-derived namespaces, bounded Store operations, and tests. Do not add RLS,
direct SQL adapters, extra graphs, or a second Store to pretend otherwise.

## Why ownership is required

Runtime DML alone could use table grants, but Agent Server applies startup
schema migrations. PostgreSQL does not grant `ALTER TABLE` as an independent
privilege: it follows object ownership. The narrowly scoped role therefore owns
the Agent Server schema objects, but not the database, extensions,
`session_catalog`, server files, replication, or roles. The observed extensions
remain operator-owned. Any Agent Server upgrade that changes extension
requirements must be rehearsed on a restored clone before production rollout.

This conclusion is valid for the audited schema and deployed
`langgraph-api==0.13.0`; official documentation asks operators to grant the
principal only the permissions Agent Server needs but does not publish a stable,
versioned relation/grant manifest.

## Later rollout prerequisites (not performed)

1. Obtain explicit human release approval and a maintenance window. Drain runs
   and take a verified backup or volume snapshot; test restore to a separate
   database first.
2. Re-run the read-only catalog inventory and compare it with the exact object
   allowlist in `phase5_least_privilege.sql`. Rehearse the pinned image startup,
   migrations, Store operations, checkpoints, and session catalog against that
   restored clone using the proposed roles.
3. Choose fresh role names and provision authentication material out of band.
   Do not put it in this repository or command history. The SQL artifact creates
   roles without embedding authentication material.
4. As the current object owner, apply the artifact once with `psql` variables,
   for example by mapping protected environment values into `-v database_name`,
   `-v agent_server_role`, and `-v session_catalog_role`. Do not interpolate
   role names into a generated SQL file.
5. In one approved deployment change, set the standalone Agent Server's
   `DATABASE_URI` to the Agent Server role and the application's `POSTGRES_URI`
   to the catalog role. Resolve/remove the repository's duplicate database URI
   aliases so the runtime cannot select the old superuser URI. Keep the same
   database, named volume, and service topology.
6. Restart only as an explicitly approved rollout step (no rebuild is required),
   then run read-only ownership/attribute checks plus focused write/read/delete
   probes through public APIs. Verify old threads, checkpoints, Store records,
   and session-catalog views before declaring success.
7. Roll back credentials/configuration and ownership grants only from a reviewed
   inverse plan. Never recreate the database or volume and never import or merge
   checkpoint state.

## Official references

- Standalone Agent Server and `DATABASE_URI` responsibilities:
  https://docs.langchain.com/langsmith/deploy-standalone-server
- PostgreSQL/Redis IAM authentication and the distinction between authentication
  and database grants: https://docs.langchain.com/langsmith/configure-iam-auth
- Self-hosted Agent Server environment variables and version requirements:
  https://docs.langchain.com/langsmith/env-var-self-hosted
- Agent Server-managed persistence and Store/checkpointer distinction:
  https://docs.langchain.com/oss/python/langgraph/persistence
- Different database per deployment:
  https://docs.langchain.com/langsmith/self-hosted-platform-features
