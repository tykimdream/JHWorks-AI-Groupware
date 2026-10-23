-- Initial common fixtures for the isolated synthetic demo only.
-- No credentials, private data copy, embedding/provider calls, UPDATE or DELETE.
-- One atomic DO: existing common data is rejected rather than overwritten.
DO $demo_common$
BEGIN
    IF current_database() NOT IN ('postgres', 'jhworks_test')
       OR current_user NOT IN ('postgres', 'jhworks_test') THEN
        RAISE EXCEPTION 'Use the approved operator and database';
    END IF;
    IF NOT pg_try_advisory_xact_lock(hashtext('jhworks-demo-common-v1')) THEN
        RAISE EXCEPTION 'Common fixture initialization is busy';
    END IF;
    IF (SELECT pg_get_userbyid(nspowner) FROM pg_namespace
        WHERE nspname = 'groupware_demo') IS DISTINCT FROM 'jhworks_demo_migrate' THEN
        RAISE EXCEPTION 'Expected the dedicated demo schema owner';
    END IF;
    IF (SELECT version_num FROM groupware_demo.alembic_version)
       IS DISTINCT FROM 'f30c9a71b624' THEN
        RAISE EXCEPTION 'Expected the verified demo migration head';
    END IF;
    IF (SELECT count(*) FROM pg_roles
        WHERE rolname IN ('jhworks_demo_runtime', 'jhworks_demo_migrate') AND rolcanlogin) <> 2
       OR has_schema_privilege('jhworks_demo_runtime', 'groupware', 'USAGE')
       OR has_schema_privilege('jhworks_demo_migrate', 'groupware', 'USAGE') THEN
        RAISE EXCEPTION 'Expected authenticated isolated demo roles';
    END IF;
    IF EXISTS (SELECT 1 FROM groupware_demo.credentials) THEN
        RAISE EXCEPTION 'Password credentials do not belong in this demo';
    END IF;
    IF EXISTS (SELECT 1 FROM groupware_demo.company_policies)
       OR EXISTS (SELECT 1 FROM groupware_demo.policy_sections)
       OR EXISTS (SELECT 1 FROM groupware_demo.work_calendar_events WHERE scope = 'COMPANY') THEN
        RAISE EXCEPTION 'Common data already exists; inspect before any repeat';
    END IF;

    INSERT INTO groupware_demo.company_policies
        (record_id, policy_id, type, title, version, status, effective_from,
         content_hash, created_at, published_at)
    VALUES ('demo_policy_travel_v1', 'demo_policy_travel', 'TRAVEL', '[체험·합성] 국내 출장 규정', 'demo-1.0', 'ACTIVE',
        date_trunc('year', CURRENT_DATE)::date, '204110336c637f81fc31fd508d9dd00367ec4fabc771ebbe7f0d85106a443a47', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO groupware_demo.policy_sections
        (policy_record_id, section_id, title, content, "order", rule_config)
    VALUES
        ('demo_policy_travel_v1', 'TRAVEL-1', '숙박비', '국내 출장 숙박비는 1박당 120,000원까지 정산합니다.', 1, '{"kind":"MAX_LODGING_PER_NIGHT","limitKrw":120000}'::json),
        ('demo_policy_travel_v1', 'TRAVEL-2', '교통비', '교통비는 증빙한 실제 비용을 정산합니다.', 2, '{"kind":"ATTACHMENT_REQUIRED_WHEN_COST_POSITIVE","costField":"transportation"}'::json),
        ('demo_policy_travel_v1', 'TRAVEL-3', '사전 승인', '총 예상 비용이 300,000원 이상인 출장은 사전 승인이 필요합니다.', 3, '{"kind":"PRIOR_APPROVAL_MIN_TOTAL","thresholdKrw":300000}'::json),
        ('demo_policy_travel_v1', 'TRAVEL-4', '출장 목적', '고객 방문 출장에는 고객명과 구체적인 방문 목적을 작성합니다.', 4, NULL);

    INSERT INTO groupware_demo.company_policies
        (record_id, policy_id, type, title, version, status, effective_from,
         content_hash, created_at, published_at)
    VALUES ('demo_policy_expense_v1', 'demo_policy_expense', 'EXPENSE', '[체험·합성] 업무 경비 규정', 'demo-1.0', 'ACTIVE',
        date_trunc('year', CURRENT_DATE)::date, '06185f941392a9a01d4840d25a9022b58572acddc5e3eccec5659edbc1db3487', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO groupware_demo.policy_sections
        (policy_record_id, section_id, title, content, "order", rule_config)
    VALUES
        ('demo_policy_expense_v1', 'EXPENSE-1', '고객 식사', '고객 미팅 식사비는 참석자 1인당 50,000원까지 정산합니다.', 1, NULL),
        ('demo_policy_expense_v1', 'EXPENSE-2', '영수증', '100,000원 이상 경비에는 영수증이 필요합니다.', 2, '{"kind":"RECEIPT_REQUIRED_MIN_TOTAL","thresholdKrw":100000}'::json),
        ('demo_policy_expense_v1', 'EXPENSE-3', '사전 승인', '300,000원 이상 업무 경비는 사전 승인이 필요합니다.', 3, '{"kind":"PRIOR_APPROVAL_MIN_TOTAL","thresholdKrw":300000}'::json);

    INSERT INTO groupware_demo.company_policies
        (record_id, policy_id, type, title, version, status, effective_from,
         content_hash, created_at, published_at)
    VALUES ('demo_policy_leave_v1', 'demo_policy_leave', 'LEAVE', '[체험·합성] 연차 규정', 'demo-1.0', 'ACTIVE',
        date_trunc('year', CURRENT_DATE)::date, 'f996b5a4bd4a47793055727280c3b9fda57e62cbdcfdef4e091e6c589ee0819d', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO groupware_demo.policy_sections
        (policy_record_id, section_id, title, content, "order", rule_config)
    VALUES
        ('demo_policy_leave_v1', 'LEAVE-1', '잔여 연차', '연차는 직원의 사용 가능한 잔여 일수 안에서 신청합니다.', 1, NULL),
        ('demo_policy_leave_v1', 'LEAVE-2', '사전 신청', '연속 3일 이상 연차는 영업일 기준 5일 전에 신청합니다.', 2, NULL),
        ('demo_policy_leave_v1', 'LEAVE-3', '반차', '반차 신청은 연차 잔여 일수에서 0.5일을 차감합니다.', 3, NULL);

    -- Current and following database calendar year: 24 months, two fake events/month.
    -- These are labelled synthetic company events, not statutory public holidays.
    WITH months AS (
        SELECT (date_trunc('year', CURRENT_DATE) + make_interval(months => n))::date AS month
        FROM generate_series(0, 23) AS n
    ), events AS (
        SELECT 'demo_common_townhall_' || to_char(month, 'YYYYMM') AS id,
               'COMPANY_EVENT' AS category, '[체험·합성] 공통 타운홀' AS title,
               month + mod(4 - extract(isodow FROM month)::integer + 7, 7) + 7 AS day,
               'CAUTION' AS impact
        FROM months
        UNION ALL
        SELECT 'demo_common_holiday_' || to_char(month, 'YYYYMM'),
               'HOLIDAY', '[체험·합성] 공통 휴무',
               month + mod(3 - extract(isodow FROM month)::integer + 7, 7), 'BLOCKED'
        FROM months
    )
    INSERT INTO groupware_demo.work_calendar_events
        (id, category, title, description, start_date, end_date, scope, status, impact, created_at)
    SELECT id, category, title, 'JHWorks 개인 프로젝트의 합성 일정입니다. 실제 회사·법정 휴일이 아닙니다.',
           day, day, 'COMPANY', 'CONFIRMED', impact, CURRENT_TIMESTAMP
    FROM events;
END
$demo_common$;
