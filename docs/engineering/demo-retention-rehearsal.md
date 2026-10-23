# 전용 데모 정리 리허설 준비

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
   비활성·직원2·결재0인 최신 합성 공간 후보를 읽기만 한다. 이 SQL은 시간 변경/삭제/credential 읽기를 하지 않는다.
   후보는 자동 삭제 허가가 아니며 실제 runner의 전체 관계 검증을 대체하지 않는다.
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
5. 이어서 주기 실행/실패·누락 감지의 구체적 설정과 비용/IAM을 준비한다. Scheduler 요청 성공과
   비동기 Job 완료는 다르며, 주기 코드만으로 보관 정책 준수를 주장하지 않는다.

원격 삭제 전에는 승인과 복원 검증이 모두 필요하다. 현재 dump는 전용 demo 전체를 포함하지만
shared Supabase 원본에 통째로 복원하는 것은 별도 고위험 작업이다. 자동 rollback 수단으로 사용하지 않는다.
삭제 후 복구가 필요하면 먼저 격리 DB에 복원해 영향을 판단하고 별도 복구 절차/승인을 준비한다.
