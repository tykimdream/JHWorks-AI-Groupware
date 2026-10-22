-- Execute once as the Supabase database owner AFTER reviewing/approving grants.
-- One atomic statement. Existing target roles/schema cause failure, never adoption.
-- No passwords or LOGIN are set here. This does not copy private staging data.
DO $demo_bootstrap$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'groupware') THEN
        RAISE EXCEPTION 'Expected private staging schema is absent';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
        WHERE e.extname = 'vector' AND n.nspname = 'extensions'
    ) THEN
        RAISE EXCEPTION 'Install vector in extensions as the database owner first';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'groupware_demo')
       OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN
           ('jhworks_demo_migrate', 'jhworks_demo_runtime')) THEN
        RAISE EXCEPTION 'Demo targets already exist; inspect partial state, do not rerun';
    END IF;

    CREATE ROLE jhworks_demo_migrate NOLOGIN NOINHERIT NOSUPERUSER
        NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    CREATE ROLE jhworks_demo_runtime NOLOGIN NOINHERIT NOSUPERUSER
        NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    GRANT CONNECT ON DATABASE postgres TO jhworks_demo_migrate, jhworks_demo_runtime;
    GRANT jhworks_demo_migrate TO postgres;
    CREATE SCHEMA groupware_demo AUTHORIZATION jhworks_demo_migrate;
    REVOKE ALL ON SCHEMA groupware_demo FROM PUBLIC, anon, authenticated;
    GRANT USAGE ON SCHEMA groupware_demo TO jhworks_demo_runtime;
    GRANT USAGE ON SCHEMA extensions TO jhworks_demo_migrate, jhworks_demo_runtime;

    ALTER ROLE jhworks_demo_migrate IN DATABASE postgres
        SET search_path TO groupware_demo, extensions;
    ALTER ROLE jhworks_demo_runtime IN DATABASE postgres
        SET search_path TO groupware_demo, extensions;
    ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_demo_migrate IN SCHEMA groupware_demo
        REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
    ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_demo_migrate IN SCHEMA groupware_demo
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO jhworks_demo_runtime;
    ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_demo_migrate IN SCHEMA groupware_demo
        GRANT USAGE, SELECT ON SEQUENCES TO jhworks_demo_runtime;

    IF has_schema_privilege('jhworks_demo_runtime', 'groupware', 'USAGE')
       OR has_schema_privilege('jhworks_demo_migrate', 'groupware', 'USAGE') THEN
        RAISE EXCEPTION 'Private schema is accessible through inherited/public privileges';
    END IF;
END
$demo_bootstrap$;

-- Keep groupware_demo outside exposed Data API schemas.
-- Set independent credentials interactively only after this transaction succeeds.
