# 전용 DB·신원 전환 실제 검증 — 2026-10-23

## 적용 범위와 현재 상태

사용자가 「전용 DB로 비공개 전환 진행」을 승인한 후 [준비한 계획](demo-isolated-rollout.md)을 적용했다.
새 migration Job 1회, 기존 demo service 전환, 기존 maintenance의 전용 참조 변경/dry-run 1회다.
새 IAM/Secret version·유료 DB·Scheduler·공개 접근·DNS·LLM·실제 데이터 삭제는 적용하지 않았다.

| 대상 | 실제 결과 |
| --- | --- |
| migration | jhworks-demo-migrate-z6dqt, 성공 task1, retry0, elapsed8.180초 |
| demo revision | jhworks-demo-75d5e8a98fb2-3c51785fafdb, traffic100%, 임시 tag 제거 |
| demo 실행 계정 | jhworks-demo-runtime, 전용 runtime DB/session Secret v1 |
| migration 실행 계정 | jhworks-demo-migrate, 전용 migration DB/session Secret v1 |
| maintenance | jhworks-demo-maintenance-v4tzd, 성공 task1, retry0, elapsed8.133초 |
| 실제 앱 HTTP 검증 | 20개 통과, 합성 방문 공간2/결재1/피드백1 |
| 기존 staging | spec/revision/traffic 유지, jhworks-staging-75d5e8a98fb2 |
| 익명 요청 | staging/demo 각각 HTTP403, project/service public binding 없음 |
| domain | HTTPS200, 기존 준비 HTML hash 일치, 앱/포트폴리오 버튼 미연결 |

이미지 source는 그대로 `75d5e8a98fb2919e46958f7d580b0aa287ed3705`이며 새 도구 커밋을 이미지
source로 표시하지 않았다. API/web digest는 계획 문서와 같다. 서비스 min0/max1·concurrency4,
web/API 각 CPU1·512MiB·timeout55초·AI off·invoker IAM 검사·고정 v1 참조를 유지한다.
원격 runtime/migrate의 실제 인증/private SELECT 거부는 [credential 증거](demo-credential-setup.md)를 따른다.
이번 migration의 성공과 실제 guest DML은 전용 두 신원의 Secret 사용/DB 접근을 추가로 확인한다.

## 실행 중 확인한 Cloud Run 동작

서비스를 기존 traffic100%로 유지하며 candidate를 만들었다. 최초 검사에서 `latestReadyRevisionName`이
기존 revision이고 새 revision은 Ready=True/Retired, Active=False/ResourcesAvailable=Unknown이었다.
이 상태를 새 컨테이너의 실제 기동·DB 검증 성공으로 취급하지 않았다. 새 revision 자체와 설정을 읽고,
0% 임시 `isolation-check` tag에 인증된 readiness 요청을 보내 HTTP200/database ok를 확인했다.
이후에만 기본 traffic100%를 전환하고 임시 tag를 제거했다. 익명 공개 권한은 만들지 않았다.

Cloud Run은 입력에 없던 web port name=http1, web startup timeoutSeconds=1,
API liveness failureThreshold=3을 응답에 추가했다. 초기 전체 dict 동일성 검사는 이를 허용하지 않아
중단됐다. 정확한 세 기본값을 확인한 뒤 그 필드만 제외해 container image/env/resources/probe 나머지를
대조했다. 검사를 무조건 통과시키거나 candidate를 재배포하지 않았다. 이 사건은 앱 장애나 migration
실패가 아니라 운영 검증기의 잘못된 기준이었다. 실패 기록과 후속 실제 검증을 별도로 보관했다.

HTTP 검증 실패 시 이전 revision traffic100% 복구를 준비했으나 실제로는 모두 통과해 실행하지 않았다.
따라서 이번 결과를 실제 rollback drill이나 DB 복원 성공으로 표현하지 않는다.

## DB 보존 비교

[읽기 전용 비교 SQL](../../deploy/cloud-run/verify-isolated-data.sql)을 기존 postgres 운영자 UI에서
migration 전·후, HTTP 검증 후, maintenance 후 실행했다. 결과에는 원문 행/비밀번호/키를 반환하지 않는다.

| 항목 | 이전 | 이후 |
| --- | --- | --- |
| 비교한 private 테이블 / 총 행 | 16 / 64 | 16 / 64 |
| private migration head | f30c9a71b624 | f30c9a71b624 |
| private data fingerprint | 788dd33280257ec9b390ce8d64b5f3da | 동일 |
| demo 테이블 / head | 0 / 없음 | 16 / f30c9a71b624 |
| demo 방문 공간 / 결재 / 피드백 | 0 / 0 / 0 | 2 / 1 / 1 |

fingerprint는 테이블별 row JSON을 정렬·MD5 집계한 소규모 합성 fixture의 변경 감지 값이다.
DB 전체 byte/sequence/ACL·backup/restore 증거, 암호학적 무결성 보장, 대용량 성능 측정이 아니다.
실제 고객 데이터에 이 전체 집계 쿼리를 그대로 적용하지 않는다. 기존 backup은 새 demo schema와
이번 데이터를 포함하지 않으므로 공개 전 운영 단계에서 별도 backup/restore를 준비한다.

## 실제 HTTP 재현과 유지보수

[검증 스크립트](../../deploy/cloud-run/verify-isolated-demo.py)의 실제 실행 SHA256:
`643f28493cdfb93d4c380b44394b332760d53b94f3bfbf339dd3518055cc9ecc`.
현재 고정 project/revision·전용 SA/두 v1 참조·AI off/max1·서비스 IAM 검사 뒤에만 Google ID token을
메모리에서 얻어 X-Serverless-Authorization으로 사용한다. key/payload/password는 읽지 않고
token/cookie/응답 원문은 결과에 저장하지 않는다. 출력 파일이 있으면 새 방문자를 다시 만들지 않는다.
실행 전 전체 project IAM과 배포 계획 사전 조건도 확인해야 한다. 이 스크립트가 그 절차를 대체하지 않는다.

```sh
cd <검증된-source>/apps/api
uv run --frozen python ../../deploy/cloud-run/verify-isolated-demo.py \
  --apply --output <새로운-결과-file.json>
```

이 명령은 읽기 전용이 아니다. 합성 공간2·결재1·피드백1을 만들므로 현재 결과를 보기 위해 재실행하지
않는다. 후속 실행은 날짜/쓰기 예산과 기존 결과를 조사하고 승인된 범위에서만 진행한다.

실제 20개 검사: ready/configuration, 첫 방문·Secure/HttpOnly/SameSite cookie·me, 잘못된 Origin403,
일반 결재 draft201/submit/manager/assigned/approve/author 복귀, 피드백200·중복 동일 receipt·목록405,
두 번째 방문과 분리된 부서·다른 공간403, 두 방문자 logout200/이후me401.
이 결과는 실제 custom domain 브라우저·키보드·모바일·만료 UX 검증을 대신하지 않는다.
실제 서로 다른 환경의 HMAC 상호 거부는 아직 별도 검증 전이며 CI의 키 교체/HTTP 테스트와 구분한다.

maintenance Job 성공과 별도로 해당 execution의 애플리케이션 로그를 조회했다.
dryRun=true/status=passed, feedback stored1/expired0/removed0, workspaces planned0/removed0이었다.
만료 행이 없었으므로 실제 만료 삭제·참조 보존·예약 실행·실패/실행 누락 감지는 이번 증거에 포함되지 않는다.

로컬: 검증 스크립트 Ruff/strict mypy 및 app/tests 포함 mypy158 files 통과. target revision/SA/Secret을
잘못 쓰거나 서비스 public binding이 있으면 ID token 조회/HTTP 이전에 중단하는 회귀4개 통과(0.17초).
전체 API/PG/browser/container/dependency는 이 변경 PR의 정확한 head CI와 리뷰 기록을 따른다.

## 비용·기록·다음 단위

elapsed 값은 GCP execution startTime~completionTime이며 DB query latency나 청구 vCPU-second가 아니다.
Cloud Run Job은 최소1분 과금이 있으므로 8초 실행을 8초 청구/0원으로 해석하지 않는다.
이번 $0~$0.10 목표는 승인 당시 추정이며 실제 billing 계정 총액을 조회하지 않았다.
무료 할당은 계정 공유이며 로그/Secret 읽기/전송/세금은 별도다.
[공식 Cloud Run 가격](https://cloud.google.com/run/pricing)을 확인했고 새 LLM key/유료 DB는 없다.

Cloud Shell `~/jhworks-isolated-rollout-plan-b5492a5e1530/`에 manifest/이전 spec/attempt/실제 execution/
HTTP report/application log/final boundary/summary를 보관했다. source archive hash는
`ef5ecbecf02b602d75b7b4baf98f7bad491879de961d809beaf9ebe22496b4e7`이다.
domain 준비 HTML SHA256은 `592325ff5173961c3570c9c89d70c0a130a474ea5bc6f98ed4c21909904ce2cd`였다.
이 정보는 실제 청구·영구 보관·정기 backup을 보증하지 않는다.

다음은 합성 공용 규정·일정과 실제 키 경계 확인, 이후 정리·최소 운영·최종 QA·Hosting 공개·포트폴리오
연결이다. 공개까지의 전체 checkpoint1이나 라이브 배포 전체를 이번 작업만으로 완료 처리하지 않는다.
