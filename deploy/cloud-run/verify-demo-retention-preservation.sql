-- Read-only comparison; excludes only the approved synthetic graph and mutable feedback lock gate.
WITH fingerprints AS (
SELECT 'alembic_version' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.alembic_version t
UNION ALL
SELECT 'departments' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.departments t WHERE id <> 'demo_dept_d3cee3b5a38f4e19882035ae5fd7162b'
UNION ALL
SELECT 'employees' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.employees t WHERE demo_workspace_id IS DISTINCT FROM 'demo_d3cee3b5a38f4e19882035ae5fd7162b'
UNION ALL
SELECT 'credentials' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.credentials t
UNION ALL
SELECT 'approvals' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.approvals t
UNION ALL
SELECT 'approval_lines' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.approval_lines t
UNION ALL
SELECT 'leave_accounts' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.leave_accounts t WHERE employee_id NOT IN ('demo_author_d3cee3b5a38f4e19882035ae5fd7162b','demo_mgr_d3cee3b5a38f4e19882035ae5fd7162b')
UNION ALL
SELECT 'work_calendar_events' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.work_calendar_events t WHERE department_id IS DISTINCT FROM 'demo_dept_d3cee3b5a38f4e19882035ae5fd7162b' AND (employee_id IS NULL OR employee_id NOT IN ('demo_author_d3cee3b5a38f4e19882035ae5fd7162b','demo_mgr_d3cee3b5a38f4e19882035ae5fd7162b'))
UNION ALL
SELECT 'demo_start_budget' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.demo_start_budget t
UNION ALL
SELECT 'demo_feedback' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.demo_feedback t
UNION ALL
SELECT 'demo_workspaces' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.demo_workspaces t WHERE id <> 'demo_d3cee3b5a38f4e19882035ae5fd7162b'
UNION ALL
SELECT 'leave_agent_runs' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.leave_agent_runs t WHERE actor_id NOT IN ('demo_author_d3cee3b5a38f4e19882035ae5fd7162b','demo_mgr_d3cee3b5a38f4e19882035ae5fd7162b')
UNION ALL
SELECT 'login_budget' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.login_budget t
UNION ALL
SELECT 'company_policies' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.company_policies t
UNION ALL
SELECT 'policy_sections' AS table_name,count(*) AS row_count,md5(coalesce(string_agg(to_jsonb(t)::text,E'\n' ORDER BY to_jsonb(t)::text),'')) AS data_md5 FROM groupware_demo.policy_sections t
), summary AS (SELECT count(*) AS preserved_tables,sum(row_count) AS preserved_rows,md5(string_agg(table_name||':'||row_count::text||':'||data_md5,E'\n' ORDER BY table_name)) AS preserved_fingerprint,
(SELECT count(*) FROM groupware_demo.demo_workspaces WHERE id='demo_d3cee3b5a38f4e19882035ae5fd7162b') AS target_workspace,
(SELECT count(*) FROM groupware_demo.employees WHERE demo_workspace_id='demo_d3cee3b5a38f4e19882035ae5fd7162b') AS target_employees,
(SELECT count(*) FROM groupware_demo.departments WHERE id='demo_dept_d3cee3b5a38f4e19882035ae5fd7162b') AS target_department,
(SELECT count(*) FROM groupware_demo.leave_accounts WHERE employee_id IN ('demo_author_d3cee3b5a38f4e19882035ae5fd7162b','demo_mgr_d3cee3b5a38f4e19882035ae5fd7162b')) AS target_leave_accounts,
(SELECT count(*) FROM groupware_demo.work_calendar_events WHERE department_id='demo_dept_d3cee3b5a38f4e19882035ae5fd7162b' OR employee_id IN ('demo_author_d3cee3b5a38f4e19882035ae5fd7162b','demo_mgr_d3cee3b5a38f4e19882035ae5fd7162b')) AS target_calendar_events,
(SELECT count(*) FROM groupware_demo.demo_workspaces) AS workspaces,
(SELECT count(*) FROM groupware_demo.approvals) AS approvals,
(SELECT count(*) FROM groupware_demo.demo_feedback) AS feedback,
(SELECT revision FROM groupware_demo.demo_feedback_gate WHERE id=1) AS feedback_gate_revision
FROM fingerprints)
SELECT to_jsonb(summary) AS preservation FROM summary;
