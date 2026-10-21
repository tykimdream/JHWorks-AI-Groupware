-- Review and execute once as the Supabase database owner, not on every deploy.
-- Fresh dedicated project only. Set LOGIN passwords interactively outside Git.
-- Enable vector as the owner before the restricted migration role is used.
BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE ROLE jhworks_migrate LOGIN NOINHERIT;
CREATE ROLE jhworks_runtime LOGIN NOINHERIT;
GRANT CONNECT ON DATABASE postgres TO jhworks_migrate, jhworks_runtime;
GRANT jhworks_migrate TO postgres;
CREATE SCHEMA groupware AUTHORIZATION jhworks_migrate;
REVOKE ALL ON SCHEMA groupware FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA groupware TO jhworks_runtime;
GRANT USAGE ON SCHEMA extensions TO jhworks_migrate, jhworks_runtime;

ALTER ROLE jhworks_migrate IN DATABASE postgres
    SET search_path TO groupware, extensions, public;
ALTER ROLE jhworks_runtime IN DATABASE postgres
    SET search_path TO groupware, extensions, public;

ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_migrate IN SCHEMA groupware
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_migrate IN SCHEMA groupware
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO jhworks_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE jhworks_migrate IN SCHEMA groupware
    GRANT USAGE, SELECT ON SEQUENCES TO jhworks_runtime;

COMMIT;

-- Do not add groupware to Supabase's exposed Data API schemas.
-- Never put postgres/admin credentials or a service_role key in the browser.
