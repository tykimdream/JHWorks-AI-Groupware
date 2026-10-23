-- Read-only preparation. No expiration changes, cleanup, Secret reads or scheduling.
WITH clock AS (
  SELECT floor(extract(epoch FROM statement_timestamp()))::bigint AS now_epoch
), eligible AS (
  -- Match cleanup_expired_demo's cutoff and ordering. Do not filter out rows
  -- with approvals or malformed relationships: the runner must validate them.
  SELECT w.id, w.department_id, w.expires_at_epoch
  FROM groupware_demo.demo_workspaces w CROSS JOIN clock
  WHERE w.expires_at_epoch <= clock.now_epoch - 86400
  ORDER BY w.expires_at_epoch, w.id
), candidates AS (
  SELECT w.id, w.expires_at_epoch
  FROM groupware_demo.demo_workspaces w CROSS JOIN clock
  WHERE w.expires_at_epoch <= clock.now_epoch
    AND w.id ~ '^demo_[0-9a-f]{32}$'
    AND w.department_id = 'demo_dept_' || substring(w.id FROM 6)
    AND (SELECT count(*) FROM groupware_demo.employees e
         WHERE e.demo_workspace_id=w.id) = 2
    AND NOT EXISTS (
      SELECT 1 FROM groupware_demo.approvals a
      JOIN groupware_demo.employees e ON e.id=a.author_id
      WHERE e.demo_workspace_id=w.id
    )
  ORDER BY w.expires_at_epoch DESC, w.id
  LIMIT 1
)
SELECT jsonb_build_object(
  'observed_at_epoch',(SELECT now_epoch FROM clock),
  'demo_head',(SELECT version_num FROM groupware_demo.alembic_version),
  'workspaces',(SELECT count(*) FROM groupware_demo.demo_workspaces),
  'active_workspaces',(SELECT count(*) FROM groupware_demo.demo_workspaces WHERE is_active),
  'cleanup_eligible',(SELECT count(*) FROM eligible),
  'next_cleanup',(SELECT jsonb_build_object(
      'workspace_id',w.id,'department_id',w.department_id,
      'expires_at_epoch',w.expires_at_epoch,
      'employee_count',(SELECT count(*) FROM groupware_demo.employees e
                        WHERE e.demo_workspace_id=w.id),
      'approval_count',(SELECT count(*) FROM groupware_demo.approvals a
                        JOIN groupware_demo.employees e ON e.id=a.author_id
                        WHERE e.demo_workspace_id=w.id))
    FROM eligible w ORDER BY w.expires_at_epoch,w.id LIMIT 1),
  'next_eligible_at_epoch',(SELECT min(expires_at_epoch)+86400
                           FROM groupware_demo.demo_workspaces),
  'expired_feedback',(SELECT count(*) FROM groupware_demo.demo_feedback,clock
                      WHERE created_at_epoch <= clock.now_epoch-2592000),
  'approvals',(SELECT count(*) FROM groupware_demo.approvals),
  'feedback',(SELECT count(*) FROM groupware_demo.demo_feedback),
  'policies',(SELECT count(*) FROM groupware_demo.company_policies),
  'sections',(SELECT count(*) FROM groupware_demo.policy_sections),
  'company_events',(SELECT count(*) FROM groupware_demo.work_calendar_events WHERE scope='COMPANY'),
  'credentials',(SELECT count(*) FROM groupware_demo.credentials),
  -- This is only a possible time-boundary experiment, never an apply target.
  'candidate',(SELECT jsonb_build_object('workspace_id',id,'expires_at_epoch',expires_at_epoch,
                  'cleanup_eligible',expires_at_epoch <= (SELECT now_epoch FROM clock)-86400)
               FROM candidates)
) AS retention_preflight;
