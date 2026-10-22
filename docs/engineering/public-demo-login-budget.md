# 공개 체험 준비: 공유 로그인 처리량 제한

## 원래 문제와 완료 조건

기존 POST /api/v1/auth/login은 요청 제한 없이 DB 조회와 Argon2 검증을 수행했다.
Cloud Run 최대 인스턴스 수는 비용 상한이나 인증 요청 제한을 보장하지 않는다.
unknown email을 바꾸거나 X-Forwarded-For를 조작해도 우회할 수 없는
서비스 전체 예산을 먼저 두고, 한도 초과 요청은 비밀번호 검증 전에 429로 거부한다.
이 작업은 로그인 계산량 보호만 다룬다. 공개 계정, 방문자별 데이터 격리,
모든 API의 남용 방어, AI 연결이나 공개 IAM은 포함하지 않는다.

## 대안과 선택

- 프로세스 메모리: 단순하지만 재시작과 다중 인스턴스에서 예산이 분리된다.
- Redis/외부 rate limit: 처리량에 유리하지만 현재 규모에서 추가 운영·비용이 필요하다.
- 기존 PostgreSQL 단일 행: 작은 데모의 낮은 로그인 처리량에 적합하고 새 서비스가 필요 없다.

기본 JHWORKS_LOGIN_REQUESTS_PER_MINUTE=60, 허용 범위 1~600.
60은 실측 최적값이 아닌 초기 운영 정책이며 공개 전 부하·사용성 검증이 필요하다.
DB 시각으로 UTC 고정 분 구간을 계산하고 singleton row를
INSERT ... ON CONFLICT DO UPDATE ... WHERE ... RETURNING으로 원자적으로 갱신한다.
같은 행의 충돌은 DB가 직렬화한다. 다중 프로세스·서버가 같은 예산을 공유한다.
오래된 시각의 요청은 새 구간을 과거로 되돌릴 수 없다.

로그인 route의 첫 DB 작업으로 예산을 확정한다. 실패한 비밀번호/unknown email도
소비하므로 인증 실패의 rollback으로 카운터가 복구되지 않는다.
한도 초과는 LOGIN_RATE_LIMITED / HTTP 429 / Retry-After: 60과 no-store를 반환하며
세션을 새로 발급하지 않는다. DB 오류는 503으로 거부하고 비밀번호 검증을 진행하지 않는다.
IP·이메일·비밀번호를 카운터나 로그에 저장하지 않는다.

## 한계와 기업 운영에서의 보완

전체 공유 예산은 공격자가 정상 사용자 몫을 소진할 수 있다. 계정별 잠금이나
공정한 사용자별 quota라고 표현하지 않는다. 로그인 이후 기존 세션은 계속 사용할 수 있고
로그아웃은 제한 대상이 아니다. 고정 구간 경계에서는 짧은 시간에 최대 두 구간 몫이
처리될 수 있으므로 엄격한 rolling-minute/비용 상한이 아니다.
요청 parsing·DB 접속·거부 응답 비용은 남는다. DDoS/네트워크 보호를 대체하지 않는다.
기업 환경에서는 검증된 프록시 신원, IP/계정별 계층적 제한, WAF, 관측 지표와
사용자 복구 정책을 함께 설계한다. 규모가 커지면 이 DB 행의 경합을 측정해
외부 제한기와 token bucket/sliding window를 비교한다.

기존 데이터와 호환되는 추가 테이블 migration이다. 먼저 migration 후 앱을 배포한다.
이전 앱으로 rollback해도 테이블은 남겨두며 자동 downgrade/카운터 삭제를 하지 않는다.
운영 도구의 기대 head도 갱신한다. 기존 live backup 증거의 head는 과거 사실로 유지하고,
새 배포 전 이전 버전 도구로 backup/격리 restore를 확보한다.
새 head migration과 운영 환경 검증을 마치기 전에는 외부 배포 완료로 표시하지 않는다.

## 재현과 학습

기존 코드에서 unknown 계정의 세 번째 요청이 429 대신 401, 비밀번호 검증이
두 번 대신 세 번 실행되는 HTTP 회귀 두 건을 먼저 재현했다.
pytest tests/test_login_budget.py는 HTTP·구간 회복·실패 지속성·DB 장애를,
pytest tests/test_postgres_login_budget.py는 전용 loopback DB에서 독립 session의
동시 최초 INSERT와 기존 행 UPDATE 경쟁을 검증한다. SQLite 통과를 PostgreSQL 증거로 쓰지 않는다.

면접 질문: 왜 요청 실패에도 quota를 commit하는가? 단순 SELECT 후 UPDATE의 race는
무엇인가? 왜 사용자 제공 X-Forwarded-For를 quota key로 쓰지 않았는가?
DB가 느려지거나 공격자가 예산을 소진하면 정상 사용자에게 어떤 영향이 있는가?
직접 실습: CI의 동시 시도 수/한도를 바꾸어 승인 수가 한도를 넘지 않는지 확인하고,
고정 분 경계의 burst를 rolling-window 제한과 비교해 설명해 본다.

참고:
https://www.postgresql.org/docs/17/sql-insert.html
https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert

로컬 검증: baseline HTTP 2 failed → 수정 후 전체 API 273 passed / PostgreSQL 10 skipped (33.35초). Ruff app/tests/alembic, strict mypy app/tests 125 files, git diff --check 통과. Docker daemon은 실행 중이 아니어서 PostgreSQL 동시성은 CI 전용 loopback DB에서 실행한다. 성능 개선율은 측정하지 않았다. 실제 staging migration/배포는 아직 하지 않았다.

첫 PostgreSQL CI는 CHECK 식의 window 예약어에서 DDL 실패를 재현했다(동시성 실행 전). 아직 미배포인 신규 migration/model의 컬럼을 window_number로 변경하고 불필요한 singleton SERIAL sequence를 제거했다. 최종 PostgreSQL 결과는 정확한 후속 head의 CI에서 확인한다.

## 실제 비공개 배포와 검증 — 2026-10-22

- PR #37 최종 5139d6a: CI 5개 성공 후 자체 diff 리뷰·라벨링·병합.
  실제 PostgreSQL 17.11: 기존 목록 7건 + 신규 카운터 3건, 10 passed / 4.24초.
  validate: 273 passed / 10 skipped / 22.74초, Ruff·strict mypy 125 files 통과.
  8 workers / 24 attempts / limit 5인 신규·기존 행 경쟁 모두 승인 수와 최종 카운터가 5 이하임을 확인했다.
- 배포 SHA: 9a29f2e0c0292ec9239600f896c0f68c1fb10daf.
- 정확한 main CI: https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39728420399 성공.
- 일반 private release: https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39728919669 성공.
- Ready revision: jhworks-staging-9a29f2e0c029.
- API image: sha256:d0d3de2e77e07bee7cd7ef569d95a588c9f5e07797b987c0392a80eded8efa91.
- Web image: sha256:5e51611261083b49717f5efa806861de350f35d7c3228e97a95b89a744042317.
- migration 먼저 성공 후 새 앱으로 traffic 전환, 배포 smoke 4/4 통과.
- 새 migration head c84f2a19d6e0, login_budget 한 행과 runtime SELECT/INSERT/UPDATE/DELETE 권한 확인.
- 실제 합성 unknown 계정 로그인 한 건이 401/no-store/세션 미발급을 반환했고,
  해당 요청으로 런타임 카운터 DB 쓰기가 성공했다.
  비로그인 protected GET 401, portfolio Origin logout 403, trusted logout 200을 확인했다.
- 배포 전 백업의 각 업무 테이블 행 수·fingerprint와 배포 후 값이 모두 일치했다.
  변경 허용 범위는 alembic_version과 새 login_budget뿐이다.
- 실제 private-service 검사는 새 revision·100% traffic·비공개 IAM·max2·AI=false를 확인했다.
  쿠키 이름은 jhworks_session, origin은 기존 private Cloud Run URL을 유지했다.
- 실제 서비스에서는 60회 요청으로 quota를 소진하거나 부하 실험을 하지 않았다.
  429/구간 회복/기존 세션 보존은 재현 가능한 HTTP·PostgreSQL CI 증거이며,
  이 배포에서 실제 사용자 비밀번호를 이용한 정상 로그인·결재 흐름을 다시 실행하지 않았다.

배포 전 backup: 20261022T052814Z-09a64709, 40,814 bytes,
SHA256 432e654375b61b81e136e11a93ff9135d1bc3907b2ecadba73c79d32bf29fcea,
head b63d91e52fa0. dump 11.57초 / 격리 restore·비교 9.25초, schema/ACL/rows/sequence/head
일치 및 temporaryContainerRemoved=true. 이 숫자는 DB 성능 개선율이나 대용량 RTO가 아니다.
실제 dump는 Cloud Shell private home에만 있으며 저장소에는 넣지 않았다.

### 재현 순서와 다음 경계

1. 정확한 PR/main head CI와 postgres job에서 테스트 명령·요약을 확인한다.
2. 배포 전 버전의 staging_backup 도구로 고정된 pgvector image와 검증된 CA를 사용해
   dump·격리 restore를 실행하고 실제 backupReference를 release 입력에 연결한다.
3. 기존 cloud-run-staging workflow를 main에서 실행한다. migration 실패 시 중단,
   앱 실패 시 이전 traffic 복귀라는 기존 절차를 유지한다.
4. 새 commit을 인자로 staging_workflow의 --apply 없는 service-preflight만 실행한다.
   초기 --apply 업무 workflow는 이미 데이터가 있으므로 재실행하지 않는다.
5. 기존 Google ID token은 메모리의 X-Serverless-Authorization에만 넣고,
   정확한 private Origin으로 synthetic unknown login 한 건을 호출해 401/no-store/미발급을 확인한다.
   비밀 값과 원문 DB 행은 출력하지 않는다.
6. migration DB role의 verify-full TLS, read-only repeatable-read snapshot에서
   기존 backup의 업무 fingerprint와 비교한다. counter/head 변경을 업무 변경으로 오해하지 않는다.

도메인의 준비 화면은 그대로이며 Firebase rewrite·공개 IAM·새 사용자 인증정보·AI key를
추가하지 않았다. 새 과금 실측은 없고 기존 종량제·budget alert의 한계는 유지된다.
다음 단위는 방문자별 데이터/역할 경계, 세션 만료·생성량·쓰기량·초기화 정책을
현재 API별 권한에 맞춰 검증하는 것이다. 이 로그인 예산만으로 공개 준비 완료라고 판단하지 않는다.

배포 후 새 head의 backup/격리 restore도 성공했다: 20261022T054016Z-80debf70, 42,193 bytes, SHA256 6f85034c7394a8d8d5a8923ce34306842b2de5059c0b84e4a78de2337658a130, head c84f2a19d6e0. 12 tables(새 login_budget 1행 포함)의 schema/ACL/rows/sequence/head 비교, temporaryContainerRemoved=true. dump 11.83초 / restore 9.51초. 다음 배포용 참조: cloud-shell:20261022T054016Z-80debf70:sha256:6f85034c7394a8d8d5a8923ce34306842b2de5059c0b84e4a78de2337658a130:restore-verified. 장기/예약 백업이 아닌 수동 검증이며 다음 변경 전 상태를 다시 점검한다.
