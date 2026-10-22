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
