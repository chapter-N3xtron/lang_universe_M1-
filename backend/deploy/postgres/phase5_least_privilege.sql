\set ON_ERROR_STOP on

-- PREPARATION ARTIFACT ONLY. Run only during an explicitly approved rollout.
-- Required psql variables: database_name, agent_server_role, session_catalog_role.
\if :{?database_name}
\else
  \echo 'missing required psql variable: database_name'
  \quit 3
\endif
\if :{?agent_server_role}
\else
  \echo 'missing required psql variable: agent_server_role'
  \quit 3
\endif
\if :{?session_catalog_role}
\else
  \echo 'missing required psql variable: session_catalog_role'
  \quit 3
\endif

BEGIN;

-- Fail closed if this is not the expected existing database or either name is
-- already in use. Fresh names avoid silently inheriting memberships or settings.
SELECT set_config('phase5.database_name', :'database_name', false);
SELECT set_config('phase5.agent_server_role', :'agent_server_role', false);
SELECT set_config('phase5.session_catalog_role', :'session_catalog_role', false);
DO $variables$
BEGIN
    IF current_database() <> current_setting('phase5.database_name') THEN
        RAISE EXCEPTION 'connected database does not match database_name';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = current_setting('phase5.agent_server_role')
    ) THEN
        RAISE EXCEPTION 'agent_server_role already exists';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = current_setting('phase5.session_catalog_role')
    ) THEN
        RAISE EXCEPTION 'session_catalog_role already exists';
    END IF;
END
$variables$;

-- These are the exact Agent Server relations observed in public on the Phase 5
-- audit. Ownership checks prevent accidentally taking unrelated objects.
DO $preflight$
DECLARE
    unexpected text;
BEGIN
    SELECT string_agg(expected.name, ', ' ORDER BY expected.name)
      INTO unexpected
      FROM (VALUES
          ('assistant'), ('assistant_versions'), ('checkpoint_blobs'),
          ('checkpoint_delete_queue'), ('checkpoint_writes'), ('checkpoints'),
          ('cron'), ('run'), ('schema_migrations'), ('store'), ('thread'),
          ('thread_ttl')
      ) AS expected(name)
      LEFT JOIN pg_class c
        ON c.relname = expected.name
       AND c.relnamespace = 'public'::regnamespace
       AND c.relkind IN ('r', 'p')
      LEFT JOIN pg_roles owner_role ON owner_role.oid = c.relowner
     WHERE c.oid IS NULL OR owner_role.rolname <> current_user;
    IF unexpected IS NOT NULL THEN
        RAISE EXCEPTION 'missing or not owned by rollout role: %', unexpected;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = 'checkpoint_delete_queue_id_seq'
           AND c.relkind = 'S'
           AND pg_get_userbyid(c.relowner) = current_user
    ) THEN
        RAISE EXCEPTION 'missing or not owned by rollout role: checkpoint_delete_queue_id_seq';
    END IF;

    IF pg_get_userbyid((SELECT nspowner FROM pg_namespace WHERE nspname = 'public'))
       NOT IN (current_user, 'pg_database_owner') THEN
        RAISE EXCEPTION 'public schema has an unexpected owner';
    END IF;

    IF pg_get_userbyid((SELECT nspowner FROM pg_namespace WHERE nspname = 'session_catalog'))
       <> current_user THEN
        RAISE EXCEPTION 'session_catalog schema is not owned by the rollout role';
    END IF;
END
$preflight$;

SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
    :'agent_server_role'
)
\gexec
SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
    :'session_catalog_role'
)
\gexec

REVOKE ALL ON DATABASE :"database_name" FROM :"agent_server_role";
REVOKE ALL ON DATABASE :"database_name" FROM :"session_catalog_role";
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE :"database_name" TO :"agent_server_role";
GRANT CONNECT ON DATABASE :"database_name" TO :"session_catalog_role";

-- Agent Server migration and runtime authority. Index ownership follows tables.
ALTER SCHEMA public OWNER TO :"agent_server_role";
ALTER TABLE public.assistant OWNER TO :"agent_server_role";
ALTER TABLE public.assistant_versions OWNER TO :"agent_server_role";
ALTER TABLE public.checkpoint_blobs OWNER TO :"agent_server_role";
ALTER TABLE public.checkpoint_delete_queue OWNER TO :"agent_server_role";
ALTER SEQUENCE public.checkpoint_delete_queue_id_seq OWNER TO :"agent_server_role";
ALTER TABLE public.checkpoint_writes OWNER TO :"agent_server_role";
ALTER TABLE public.checkpoints OWNER TO :"agent_server_role";
ALTER TABLE public.cron OWNER TO :"agent_server_role";
ALTER TABLE public.run OWNER TO :"agent_server_role";
ALTER TABLE public.schema_migrations OWNER TO :"agent_server_role";
ALTER TABLE public.store OWNER TO :"agent_server_role";
ALTER TABLE public.thread OWNER TO :"agent_server_role";
ALTER TABLE public.thread_ttl OWNER TO :"agent_server_role";

-- Existing application-owned query projection uses POSTGRES_URI separately.
ALTER SCHEMA session_catalog OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.activity_intervals OWNER TO :"session_catalog_role";
ALTER SEQUENCE session_catalog.activity_intervals_interval_id_seq OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.agent_participations OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.artifacts OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.projection_migrations OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.session_artifact_links OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.sessions OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.summary_revisions OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.tent_poles OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.workspace_session_links OWNER TO :"session_catalog_role";
ALTER TABLE session_catalog.workspaces OWNER TO :"session_catalog_role";

-- The default public schema already denies CREATE to PUBLIC in the observed DB;
-- repeat that invariant explicitly while preserving public USAGE for extensions.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA session_catalog FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public, session_catalog FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public, session_catalog FROM PUBLIC;

COMMIT;
