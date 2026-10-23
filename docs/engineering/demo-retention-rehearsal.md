# 전용 데모 정리 리허설 준비

## 2026-10-23 18:34 KST 이후 읽기 재검증

운영 Cloud Shell에 저장돼 있던 오전 실행 보고서를 발견하고 실제 Cloud Run execution과
Cloud Logging을 읽어 대조했다. 아래 리허설은 이번 후속 작업에서 새로 실행한 것이 아니다.
아래 본문의 '아직 실행하지 않았다'는 이전 준비 시점의 기록이다.

| 단계 | 기존 execution | 완료 시각 KST | 앱 결과 |
| --- | --- | --- | --- |
| dry-run / batch1 | `jhworks-demo-maintenance-mp62b` | 2026-10-23 11:31:29 | workspace planned1/removed0 |
| apply / batch1 | `jhworks-demo-maintenance-22s54` | 2026-10-23 11:33:41 | workspace planned1/removed1 |
| apply 재실행 / batch1 | `jhworks-demo-maintenance-7vk85` | 2026-10-23 11:35:31 | workspace planned0/removed0 |

각 execution은 succeeded1/failed0이고 완료 시각이 저장된 `step-N.json`과 일치했다.
각 execution의 로그에서 앱 보고서가 정확히1개 조회됐고 저장 보고서와 내용이 같았다.
세 실행 모두 feedback expired0/removed0/stored1이다. 이 결과는 만료 피드백의 실제 삭제 증거는 아니다.
기존 보고서는 `~/jhworks-demo-retention-rehearsal/`의 `step-1.json`~`step-3.json`,
`step-N-execution.json`, `final-boundary.json`에 있다.

현재 Job은 전용 runtime SA와 전용 DB/session Secret v1, CPU1/512Mi/timeout120/retry0,
기본 `--batch-size 5`/dry-run을 유지하는 것으로 읽기 확인했다. 현재 Job 설정의 이미지 참조는
`sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0`이고,
조회한 세 execution의 이미지 참조는
`sha256:dbb7df278f586b6ff32e32cd13e9218b72f10af57f490aab36e5b3437a87fb5f`다.
두 digest의 manifest 관계/source 동일성은 이번 조회만으로 단정하지 않는다.

기존 `final-boundary.json`은 Job 기본값/private revision/준비 화면 유지, 익명403 두 건,
AI off, operator Secret payload 읽기0을 기록한다. 이 파일을 읽은 것을 새로운 DB fingerprint
비교나 새로운 domain HTTP 검증으로 표현하지 않는다. 백업 보고서의 passed/격리 컨테이너 제거 기록도 확인했다.
원격 DB의 현재 관계·행 보존 재대조와 원래 삭제 대상/시간 조정의 근거는 별도 확인이 필요하다.
추가 Job 실행·삭제·Secret payload 읽기·권한 변경·Scheduler 생성은 이번 읽기 재검증에 포함하지 않았다.

다음 작업은 이 증거를 기준으로 원격 키 경계 확인과 정리 주기·실패/누락 감지를 준비하는 것이다.
같은 정리 리허설을 무조건 다시 실행하지 않는다.

## 현재 완료와 다음 문제

전용 demo migration/runtime 경계와 공용 자료/업무 HTTP, maintenance dry-run/삭제0,
새 demo16테이블85행의 [백업·격리 복원](demo-backup-profile.md)은 실제 통과했다.
기존 runner의 실제 PostgreSQL CI는 FK 순서·피드백 보존 기간·재실행0·private 행 보존·timeout을
검증하지만 hosted DB에서 실제 만료 공간을 정리한 증거와 주기/실패 감지는 아직 없다.

기존 `cleanup_expired_demo`의 만료 후24시간 조건과 관계 검증을 유지한다.
그 시간을 줄이거나 원격 DB에서 로컬 seed를 실행하지 않는다. 매번 새 키/계정/서비스를 만들 필요도 없다.
정리 CLI/이미지/기존 전용 maintenance Job을 재사용한다.

## 실제 삭제 전 준비와 적용 gate

1. `deploy/cloud-run/verify-demo-retention.sql`로 head/현재 건수/자연 만료24h 대상/30일 피드백,
   세션 만료·직원2·결재0인 최신 합성 공간 후보를 읽기만 한다. 이 SQL은 시간 변경/삭제/credential 읽기를 하지 않는다.
   후보는 자동 삭제 허가가 아니며 실제 runner의 전체 관계 검증을 대체하지 않는다.
   `next_cleanup`은 실제 runner와 같은 만료24h cutoff·만료 epoch/ID 오름차순의 첫 대상이다.
   `candidate`는 시간 경계 실험 후보이며 runner 대상과 다를 수 있다. apply 대상 판단에 대신 사용하지 않는다.
   `next_eligible_at_epoch`은 가장 이른 만료 epoch+24h이며 이미 지난 값일 수 있다.
   `observed_at_epoch`과 함께 보아 대기 필요 여부를 판단한다.
2. 자연 만료 대상이 없으면 기다리거나, 별도 승인 후 로그아웃된 합성 검증 공간1개의 expiry를
   과거로 조정하는 장애/시간 경계 실험을 선택한다. 이를 실제로24시간 운영한 증거로 표현하지 않는다.
   적용 직전에 정확한 공간 ID·기존 epoch·관계·backup ID를 고정하고 조건이 바뀌면 중단한다.
   현재 이 변경 SQL/실제 삭제는 실행하지 않았다.
3. 기존 `jhworks-demo-maintenance`는 기본 dry-run을 유지한다. 검증한 기존 이미지/전용 runtime 계정/
   runtime DB·session Secret v1/CPU1·512MiB/120초/retry0를 다시 확인한다.
   1회 실행 override의 batch-size1로 dry-run→승인된 apply→재실행0을 최대3회 확인하는 안을 준비한다.
   추가 실행/과금·Secret 사용·실제 삭제 범위는 실행 직전 별도 확인한다. Job 기본값·Scheduler는 바꾸지 않는다.
4. dry-run 대상이 정확히1이고 만료 피드백0인 경우만 적용한다. 기존 결재1/피드백1·공용3/10/48·나머지 공간,
   private head/데이터 fingerprint를 전후 비교한다. 실제 JSON과 Cloud Run execution 종료 결과를 함께 본다.
   실패/비정상 건수 시 자동 반복·다른 공간 선택·원격 restore를 하지 않는다.
   SQL의 `next_cleanup.workspace_id`와 삭제 승인 대상을 맞추고, 정리 가능 건수가1인지 실행 직전에 다시 확인한다.
   `SKIP LOCKED`를 쓰는 runner는 동시 실행 시 다음 공간을 선택할 수 있으므로 다른 정리 execution이 없는지도 확인한다.
   이 SELECT는 잠금이나 실행 시점의 대상 고정을 보장하지 않는다.
5. 이어서 주기 실행/실패·누락 감지의 구체적 설정과 비용/IAM을 준비한다. Scheduler 요청 성공과
   비동기 Job 완료는 다르며, 주기 코드만으로 보관 정책 준수를 주장하지 않는다.

원격 삭제 전에는 승인과 복원 검증이 모두 필요하다. 현재 dump는 전용 demo 전체를 포함하지만
shared Supabase 원본에 통째로 복원하는 것은 별도 고위험 작업이다. 자동 rollback 수단으로 사용하지 않는다.
삭제 후 복구가 필요하면 먼저 격리 DB에 복원해 영향을 판단하고 별도 복구 절차/승인을 준비한다.

2026-10-23 첫 실제 사전 SELECT에서 workspaces3/active flag3/24h cleanup eligible0/30일 expired feedback0을
확인했다. 로그아웃이 workspace.is_active를 false로 바꾸는 것은 아니다. 서버는 만료 epoch를 따로 검사하며
정리 조건도 그 epoch다. 초기 비활성 flag 기준 후보 조회는 null이었고, 다음 조회는 미래 세션을 고르지 않도록
실제 만료 epoch 기준으로 수정했다. 이 확인은 실제 삭제나 자연적으로24시간 경과한 운영 검증이 아니다.

## 2026-10-23 후속 준비

사전 점검의 최신 빈 공간 후보와 실제 runner의 가장 오래된 공간이 다를 수 있음을 확인해 SQL에
실제 첫 대상·직원/결재 건수·관찰 시각·정리 가능 시각을 추가했다. 승인 검토에서 다른 공간을 선택하는 실수를 줄인다.
실제 관계 안전 검사는 기존 runner가 담당하며, 이 변경은 정리기·이미지·24시간 조건을 바꾸지 않는다.
기존 PG CI 파일에 빈 DB와 만료 경계/동률 ID/결재가 있는 첫 대상/아직 정리 불가인 빈 후보를 넣는 회귀를 추가했다.
전용 runtime 역할로 실제 SQL을 실행하고 demo 전체 snapshot과 private sentinel이 보존되는지 비교한다.
원격 DB 사전 조회·삭제 리허설은 별도 실행 결과가 생기기 전까지 미완료다.
