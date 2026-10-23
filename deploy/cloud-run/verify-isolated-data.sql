-- Read-only comparison for the small synthetic rollout fixture.
-- Run as the existing operator; no raw rows, passwords or keys are returned.
WITH fingerprints AS (
SELECT 'alembic_version' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.alembic_version t
UNION ALL
SELECT 'departments' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.departments t
UNION ALL
SELECT 'employees' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.employees t
UNION ALL
SELECT 'credentials' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.credentials t
UNION ALL
SELECT 'approvals' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.approvals t
UNION ALL
SELECT 'approval_lines' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.approval_lines t
UNION ALL
SELECT 'leave_accounts' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.leave_accounts t
UNION ALL
SELECT 'work_calendar_events' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.work_calendar_events t
UNION ALL
SELECT 'demo_start_budget' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.demo_start_budget t
UNION ALL
SELECT 'demo_feedback_gate' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.demo_feedback_gate t
UNION ALL
SELECT 'demo_feedback' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.demo_feedback t
UNION ALL
SELECT 'demo_workspaces' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.demo_workspaces t
UNION ALL
SELECT 'leave_agent_runs' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.leave_agent_runs t
UNION ALL
SELECT 'login_budget' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.login_budget t
UNION ALL
SELECT 'company_policies' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.company_policies t
UNION ALL
SELECT 'policy_sections' AS table_name, count(*) AS row_count, md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text), '')) AS data_md5 FROM groupware.policy_sections t
) SELECT count(*) AS private_tables, sum(row_count) AS private_rows, md5(string_agg(table_name || ':' || row_count::text || ':' || data_md5, E'\n' ORDER BY table_name)) AS private_data_fingerprint, (SELECT version_num FROM groupware.alembic_version) AS private_head, (SELECT count(*) FROM information_schema.tables WHERE table_schema='groupware_demo') AS demo_tables, (SELECT version_num FROM groupware_demo.alembic_version) AS demo_head, (SELECT count(*) FROM groupware_demo.demo_workspaces) AS isolated_visits, (SELECT count(*) FROM groupware_demo.approvals) AS isolated_approvals, (SELECT count(*) FROM groupware_demo.demo_feedback) AS isolated_feedback, (SELECT count(*) FROM pg_roles WHERE rolname IN ('jhworks_demo_runtime','jhworks_demo_migrate') AND rolcanlogin) AS demo_login_roles FROM fingerprints;
