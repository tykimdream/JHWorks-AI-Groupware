-- Read-only checks after supabase-bootstrap.sql; every *_ok value must be true.
WITH checks AS (
SELECT
    (SELECT extversion FROM pg_extension WHERE extname = 'vector') AS vector_version,
    (SELECT pg_get_userbyid(nspowner) = 'jhworks_migrate'
       FROM pg_namespace WHERE nspname = 'groupware') AS schema_owner_ok,
    has_schema_privilege('jhworks_runtime', 'groupware', 'USAGE') AS runtime_usage_ok,
    NOT has_schema_privilege('jhworks_runtime', 'groupware', 'CREATE') AS runtime_no_ddl_ok,
    NOT has_schema_privilege('anon', 'groupware', 'USAGE') AS anon_blocked_ok,
    NOT has_schema_privilege('authenticated', 'groupware', 'USAGE') AS authenticated_blocked_ok,
    (SELECT count(*) = 2 AND bool_and(NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
                     AND NOT rolbypassrls AND NOT rolinherit AND rolcanlogin)
       FROM pg_roles WHERE rolname IN ('jhworks_runtime', 'jhworks_migrate')) AS role_boundaries_ok
)
SELECT (schema_owner_ok AND runtime_usage_ok AND runtime_no_ddl_ok AND anon_blocked_ok
        AND authenticated_blocked_ok AND role_boundaries_ok) AS all_checks_ok, *
FROM checks;
