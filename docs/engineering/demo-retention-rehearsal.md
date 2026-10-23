# 전용 데모 정리 리허설

## 현재 완료와 다음 문제

전용 demo migration/runtime 경계와 공용 자료/업무 HTTP, maintenance dry-run/삭제0,
새 demo16테이블85행의 [백업·격리 복원](demo-backup-profile.md)은 실제 통과했다.
기존 runner의 실제 PostgreSQL CI는 FK 순서·피드백 보존 기간·재실행0·private 행 보존·timeout을
검증한다. 아래 추가 승인 후 hosted DB의 실제 정리/재실행도 통과했다. 주기/실패 감지는 아직 없다.

기존 `cleanup_expired_demo`의 만료 후24시간 조건과 관계 검증을 유지한다.
그 시간을 줄이거나 원격 DB에서 로컬 seed를 실행하지 않는다. 매번 새 키/계정/서비스를 만들 필요도 없다.
정리 CLI/이미지/기존 전용 maintenance Job을 재사용한다.

## 실제 삭제 전 준비와 적용 gate

1. `deploy/cloud-run/verify-demo-retention.sql`로 head/현재 건수/자연 만료24h 대상/30일 피드백,
   세션 만료·직원2·결재0인 최신 합성 공간 후보를 읽기만 한다. 이 SQL은 시간 변경/삭제/credential 읽기를 하지 않는다.
   후보는 자동 삭제 허가가 아니며 실제 runner의 전체 관계 검증을 대체하지 않는다.
2. 자연 만료 대상이 없으면 기다리거나, 별도 승인 후 로그아웃된 합성 검증 공간1개의 expiry를
   과거로 조정하는 장애/시간 경계 실험을 선택한다. 이를 실제로24시간 운영한 증거로 표현하지 않는다.
   적용 직전에 정확한 공간 ID·기존 epoch·관계·backup ID를 고정하고 조건이 바뀌면 중단한다.
   아래 실제 결과 이전까지 변경 SQL/실제 삭제는 실행하지 않았다.
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

2026-10-23 첫 실제 사전 SELECT에서 workspaces3/active flag3/24h cleanup eligible0/30일 expired feedback0을
확인했다. 로그아웃이 workspace.is_active를 false로 바꾸는 것은 아니다. 서버는 만료 epoch를 따로 검사하며
정리 조건도 그 epoch다. 초기 비활성 flag 기준 후보 조회는 null이었고, 다음 조회는 미래 세션을 고르지 않도록
실제 만료 epoch 기준으로 수정했다. 이 확인은 실제 삭제나 자연적으로24시간 경과한 운영 검증이 아니다.

## 실제 승인·실행 — 2026-10-23

PR #54 최종 head `ec4750cb4f8ac829e5e12ba26df4bafafdb21925`의 CI39887537641 필수5개 성공,
자체 리뷰 COMMENT/라벨/병합(main `897389d`) 후 진행했다. browser의 Ubuntu 폰트 다운로드 지연은
완료까지 기다렸으며 검사 생략/실패 병합은 없었다. 독립적인 사람의 승인과 구분한다.

사용자는 특정 공간1개의 시간 경계 주입과 실제 삭제, 기존 Job 최대3회 실행/추가 비용/기존 전용
runtime·DB/session v1 사용을 승인했다. 대상은 `demo_d3cee3b5a38f4e19882035ae5fd7162b`,
이전 expiry `1792718630`, 복원 검증 backup `20261023T015811Z-653f204f`다.
즉시 다시 backup 해시/0700·0600과 Job spec SHA256
`39d513df60518ad40723fe0ede91022f88f4211813a5649437a2f97e0144a3ad` 일치를 확인했다.

단일 DO는 operator/DB/schema owner/head/현재 건수·대상 ID/이전 expiry·직원2·결재0·기존 만료24h0·
만료 피드백0을 확인하고 대상1행만 inactive/DB now-86401로 바꿨다. 조건이 다르면 예외로 rollback한다.
실행한 LF SQL SHA256은 `6859b889251332e6a45a815d7838dcba0278b580c5ee2fb622a5e27e7a42fbee`다.
이후 별도 SELECT에서 eligible_count1/only_approved_target=true를 확인한 뒤에만 실제 apply를 실행했다.
시간을 인위적으로 옮긴 경계 실험이며 자연적으로24시간 보관한 실적이 아니다.

| 순서 | 실제 execution / 완료 UTC | runner 결과 |
| --- | --- | --- |
| dry-run | `jhworks-demo-maintenance-mp62b` / 02:31:29.620520 | passed, planned1/removed0, feedback stored1/removed0 |
| apply | `jhworks-demo-maintenance-22s54` / 02:33:41.633611 | passed, planned1/removed1, feedback stored1/removed0 |
| apply 재실행 | `jhworks-demo-maintenance-7vk85` / 02:35:31.603675 | passed, planned0/removed0, feedback stored1/removed0 |

각 실행은 task1/parallelism1/CPU1/512MiB/120초/retry0/batch1이고 기존 API digest `f2c2a591…`를
재사용했다. per-execution `--args` override만 썼다. Job 기본 dry-run/batch5/spec hash는 그대로다.
각 단계 전에 marker를 만들어 중복 실행을 차단하고 직전 결과/고정 spec을 검사했다. 로그 지연 시에는
같은 execution 로그만 읽고 Job을 다시 실행하지 않았다. Cloud Run 완료 상태와 실제 애플리케이션 JSON을
모두 확인했으며 운영자 프로세스에서 Secret payload를 읽지 않고 Job의 기존 v1 주입을 사용했다.

## 실제 보존 비교와 범위

`deploy/cloud-run/verify-demo-retention-preservation.sql`은 이 고정 합성 대상만 제외하고
15개 테이블의 행을 정렬 JSON hash로 비교한다. 대상 밖 78행/fingerprint
`b074f8b53081da23c0e653de04f33255`가 전/후/재실행 후 모두 같다.
workspace1/employee2/department1/leave account2가 제거됐고 대상 calendar event는 전/후0이었다.
이 외부 실험에서 결재/일정 삭제를 검증했다고 주장하지 않는다. 기존 실제 PG 회귀가 결재선/FK와
피드백30일 만료·동시 삭제·timeout 경계를 별도로 검증한다.

나머지 공간2/결재1/피드백1, 공용 규정3/조항10/회사 일정48 유지.
피드백 admission lock gate는 apply마다 revision을 올리므로 2→3→4로 바뀌었다. 비교에서 이 운영 카운터를
명시적으로 제외했다. 재실행0은 추가 업무 자료 삭제0을 뜻하며 DB 전체가 byte 단위로 불변이라는 뜻이 아니다.
private16테이블64행/head `f30c9a71b624`/fingerprint `788dd33280257ec9b390ce8d64b5f3da`는 그대로다.
MD5 행 비교는 작은 합성 데이터 변경 탐지이며 백업·ACL/sequence 검증의 대체물이나 대량 성능 결과가 아니다.

비공개 demo/staging revision·traffic·service IAM 유지/익명 readiness 각각403, AI=false,
domain 준비 HTML의 HTTPS200/hash 불변도 실제 재확인했다. 새 자원/IAM/key/Secret version,
추가 실행4회차/Job 기본값 변경/예약/공개/AI/원격 restore는 없었다.
약8초의 실행 상태 elapsed는 시작/종료·최소1분 과금과 다르다. 실제 청구 금액은 조회하지 않았고 $0으로 단정하지 않는다.

안전한 실행 JSON/metadata/최종 경계 보고는 Cloud Shell `~/jhworks-demo-retention-rehearsal/`에 보관한다.
dump는 기존 private backup 폴더에 유지한다. 로컬 증거는 `artifacts/cloud-run/demo-retention-*-20261023.png`다.
보존 SELECT를 JSON 한 셀로 바꾸는 과정에서 CRLF 종결 변환 오류(42601)1회가 있었고 읽기만 실패했다.
LF 정규화 후 같은 조회가 성공했다. 변경/삭제 SQL 실패나 Job 재실행은 없었다.

재현할 로컬 검사는 `apps/api`에서 다음과 같다. hosted workspace를 다시 생성/시간 변경/삭제하는 명령이 아니다.

```sh
uv run pytest tests/test_demo_maintenance.py tests/test_feedback_retention.py -o addopts= -q
# 별도의 loopback disposable jhworks_test PG를 구성한 경우에만:
uv run pytest tests/test_postgres_demo_workspace.py -k 'cleanup or maintenance or retention' -o addopts= -q
```

원격 기존 Job의 1회 dry-run 인자 예시는 아래와 같다. 실제 실행은 과금되므로 별도 승인 범위에서만 사용한다.
apply는 마지막 인자 `,--apply`가 필요하며, 이 리허설을 반복 승인 없이 재실행하지 않는다.

```sh
gcloud run jobs execute jhworks-demo-maintenance \
  --project=jhworks-staging-tykimdream --region=asia-northeast3 \
  --tasks=1 --task-timeout=120s \
  --args=-m,app.ops.demo_maintenance,--batch-size,1 --wait
```

다음 완료 조건은 예약 실행과 실패/누락 알림의 실제 전달 검증이다. 새 비용/호출 계정/IAM/자동 정리 범위를
구체화한 뒤 별도 확인한다. 현재 이 실험은 수동3회이며 정기 운영이나 알림이 작동한다는 증거가 아니다.
