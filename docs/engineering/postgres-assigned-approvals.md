# PostgreSQL 배정 결재 목록 회귀

## 문제와 실제 baseline

사용자 전달 private 업무 결과는 비밀번호 교체 3개 성공 뒤 initial_author_assigned에서 실패했다.
이 stage는 결재/휴가 생성 이전이다. staging 서버 로그/SQLSTATE를 직접 읽지는 않았으므로
해당 실패의 원인을 로그로 확정했다고 표현하지 않는다.

동일한 기존 코드의 PostgreSQL 결함은 별도 CI에서 실제 재현했다.
source 611a78a895d0998ed62afffee81c9ae80195d56d,
[run 39717126428 / postgres](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39717126428/job/119621802435).
PostgreSQL 17.11, pgvector 0.8.6-pg17, 합성 직원 3명, 동시 부하 없이 7개 기능 회귀를 실행했다.
결과는 **4 failed, 3 passed / 6.53초**, UndefinedFunction과
could not identify an equality operator for type json을 확인했다.
내 목록의 빈 결과 3개는 성공했고 배정 목록 3개와 여러 회차 목록 1개가 실패했다.
이 시간은 테스트 suite 시간이며 API latency/성능 개선 수치가 아니다.

## 원인과 선택

기존 배정 목록은 ApprovalLine을 JOIN한 뒤 전체 Approval/author row에 DISTINCT를 걸었다.
Approval.details/attachment_metadata가 PostgreSQL json이므로 전체 row의 동일성 비교에서 실패한다.
SQLite에서는 JSON 저장·비교 구현이 달라 기존 테스트가 이를 드러내지 못했다.

Approval.lines.any(ApprovalLine.approver_id == actor.id)는 상관 EXISTS로 변환된다.
문서마다 해당 사용자의 결재선 존재 여부만 검사하므로 outer row가 여러 회차만큼 늘어나지 않는다.
JSON 비교가 필요 없고 기존 scope/updated_at 정렬·전체 결재 회차/JSON 응답·권한을 유지한다.

- JSONB 전환은 데이터 migration·JSON 동작 범위를 넓혀 이 조회 결함의 최소 수정으로 선택하지 않았다.
- DISTINCT ON(id)은 PostgreSQL 전용 구문/정렬 제약을 도입하므로 제외했다.
- ID subquery도 가능하지만 존재 여부를 직접 표현하는 EXISTS를 선택했다.
- 기존 approver_id/approval_id 인덱스를 유지한다. 현재 변경에 새로운 성능 수치를 주장하지 않는다.

## 재현과 테스트 경계

CI postgres job은 기존 Compose와 같은 pgvector/PG17 이미지를 사용한다.
loopback의 jhworks_test 전용 DB/user만 허용하며 운영/Supabase URL은 받지 않는다.
테스트마다 UUID schema를 만들고 schema_translate_map으로 모든 ORM table을 그 schema에 고정한다.
finally에서 생성한 schema만 제거한다. 다른 schema의 table을 truncate/drop하지 않는다.
운영 credential·LLM·외부 유료 자원을 사용하지 않는다. CI 서비스 비밀번호는 합성 전용 값이다.

7개 테스트는 세 계정의 mine/assigned 빈 목록, 일반 결재 생성→상신→반려→수정→재상신 후
중복 없는 한 문서·회차 2개·JSON/첨부 보존·비참여자 목록 격리와 상세 403을 확인한다.
CI는 DB URL을 명시하고 tests/test_postgres_approval_lists.py를 직접 실행한다.
로컬 DB 미설정 시 7개는 skip이며 PostgreSQL 통과로 집계하지 않는다.
이번 테스트는 실제 ORM query/API의 PostgreSQL 호환성 검증이며 Alembic migration 검증은
기존 container-smoke와 구분한다. 동시 transaction/대량 성능 검증도 별도다.

로컬 Docker daemon을 사용할 수 없어 PostgreSQL baseline은 CI의 폐기 가능한 DB에서 실행했다.
수정 후 동일 CI 7개 결과와 main 배포·실제 private 업무 재검증을 별도로 기록한다.
비밀번호 교체는 이미 성공했으므로 재배포 뒤 교체 명령을 재실행하지 않는다.

## 학습

SQLite 단위 테스트 성공은 운영 DB dialect의 JSON/DISTINCT 계약을 보장하지 않는다.
관계의 존재를 묻는 필터는 row 확장/중복 제거보다 EXISTS로 모델링할 수 있다.
실제 기업에서도 빠른 단위 테스트와 동일 DB engine의 소수 계약 테스트를 함께 유지한다.
면접에서는 여러 결재 회차의 중복 원인, JOIN/DISTINCT와 EXISTS 차이, JSON과 JSONB 차이,
진짜 PostgreSQL 검증과 단순 SQL 문자열 테스트의 차이를 이 회귀로 설명할 수 있다.

근거: [PostgreSQL JSON 비교 연산](https://www.postgresql.org/docs/17/functions-json.html),
[SELECT DISTINCT](https://www.postgresql.org/docs/17/queries-select-lists.html).

수정 후 로컬: cp949 기본 모드 API 250 passed, 7 PostgreSQL skipped / 24.43초,
Ruff와 strict mypy 117 source files 통과. 실제 PostgreSQL 수정 후 결과는
[PR #29 CI](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/29/checks)에서 확인하며
postgres 포함 5개 검사 성공 전에는 병합하지 않는다. 테스트 재현과 live staging 성공은 구분한다.
