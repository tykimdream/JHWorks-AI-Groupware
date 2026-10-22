# 피드백 보관 정리의 실행 계약

## 문제와 선택

기존 운영 CLI는 먼저 만료 행 수를 읽고 DELETE한 뒤 처음 읽은 수를 `removed`로 출력했다.
두 운영자가 동시에 실행하면 같은 행을 각자 삭제했다고 보고할 수 있다. 삭제와 보고가 같은
트랜잭션에서 실패하거나 재실행돼도 정확한 결과를 남기는 것이 이번 단위의 완료 조건이다.

기존 피드백 접수의 singleton gate를 정리에도 재사용한다. PostgreSQL의 UPSERT 행 잠금을
트랜잭션 종료까지 유지해 여러 인스턴스의 접수/정리를 직렬화하고, DELETE RETURNING으로
실제 지워진 행만 센다. 추가 큐·Redis·분산 잠금 서비스는 300건 상한의 현재 규모에 불필요하다.
장시간 DB 트랜잭션이나 연결 장애가 있으면 잠금 대기가 생길 수 있으므로 주기 작업의 timeout과
실패 알림은 별도 운영 검증이 필요하다. 애플리케이션 인스턴스 내 mutex로는 다중 실행을 막을 수 없다.

서비스는 새 Session만 받아 다른 업무 변경을 함께 commit하지 않는다. 기본 dry-run은 rollback하며,
실제 실행의 commit 실패도 rollback하고 성공 결과를 반환하지 않는다. CLI는 예외 원문이나 피드백
내용 대신 errorType만 출력하고 종료 코드 1을 반환한다.

## 재현과 검증

```sh
cd apps/api
uv run pytest tests/test_feedback_retention.py tests/test_demo_feedback.py -o addopts= -q
uv run pytest tests/test_postgres_demo_workspace.py -o addopts= -q
```

- 로컬 SQLite: 관련 15개 통과. 30일 경계 포함/직전 제외, dry-run 보존, 재실행 0건,
  commit 실패 복구, 호출자 미저장 변경 거부, 운영 오류 원문 미노출을 검증했다.
- PostgreSQL 회귀 추가: 별도 연결 8개가 동시에 정리해 3건을 정확히 한 번만 보고하는지 검사한다.
  실제 실행 결과는 PR CI에 남기며 SQLite 통과를 PostgreSQL 동시성 증거로 해석하지 않는다.
- 새 migration, 의존성, 인증정보, 외부 유료 자원은 없다.
- 로컬 전체 API 386 passed/19 skipped (38.65초), Ruff app/tests/alembic,
  strict mypy app/tests 145 files 통과. PostgreSQL 19개 skip은 로컬 DB 미연결이며 CI에서 별도 실행한다.

## 운영 적용과 남은 조건

```sh
# 기존 공개 데모 전용 환경에서만 실행 가능. 기본은 조회/계획이다.
python -m app.ops.demo_feedback --purge-expired
# 실제 삭제는 운영 적용 승인 이후 실행한다.
python -m app.ops.demo_feedback --purge-expired --apply
```

이번에는 원격 피드백 삭제나 예약 작업을 실행하지 않았다. 접수 화면의 최대 30일 보관 안내를
실제 운영 약속으로 지키려면 공개 전용 DB/실행 계정과 주기적 실행·실패 감지·합성 만료 자료의
삭제 증거가 먼저 필요하다. 주기 실행의 간격과 장애 시 보관 초과 가능성도 검토해야 한다.
정리 코드만 존재하는 상태를 자동 보관 정리 완료로 표시하지 않는다. 실제 사용자 의견은 아직 없다.

면접/실습: 두 연결에서 COUNT와 DELETE를 분리했을 때 보고 수가 실제 삭제 수와 달라지는 순서를
그려보고, RETURNING만 적용할 때와 gate도 재사용할 때 접수 상한·보고 시점이 어떻게 달라지는지
설명한다. 실패한 commit을 성공으로 기록하면 운영자가 어떤 잘못된 판단을 하는지도 확인한다.
