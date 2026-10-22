# 공개 데모의 DB·실행 신원 분리

## 문제와 선택

비공개 리허설은 기존 runtime DB/session Secret v1을 재사용하도록 승인받았다.
인터넷 공개에서는 같은 서명키와 DB 역할을 계속 사용하면 public API의 실수가 private schema까지
영향을 줄 수 있다. 애플리케이션 workspace 필터만으로 이 경계를 보증하지 않는다.

기존 Supabase Free 프로젝트 안에 `groupware_demo` schema와 전용 migration/runtime 역할을 만들고,
GCP 실행 계정 2개·Secret 3개를 분리하는 방식을 준비한다. 별도 DB 프로젝트는 장애·관리자 경계까지
분리하는 대안이지만, 개인 데모의 현재 규모에서 별도 운영 대상과 데이터 복제를 늘리지 않는 쪽을 선택한다.
같은 DB의 schema는 CPU/스토리지/관리자·백업 장애를 분리하지 않는다. 실제 고객 데이터나 강한 tenant
격리가 필요한 기업 운영이라면 별도 DB/project 등 더 강한 경계를 다시 검토해야 한다.

새 패키지, microservice, 공개 IAM, Firebase rewrite는 이번 코드에 추가하지 않는다.
기존 private staging의 역할·Secret·배포 workflow는 유지한다.

## 검토할 구체적 변경

| 계층 | 새 대상 | 허용 범위 |
| --- | --- | --- |
| PostgreSQL | groupware_demo | 신규 빈 schema, private groupware 데이터 복사 없음 |
| PostgreSQL | jhworks_demo_migrate | demo schema 소유/DDL, extensions USAGE, private schema 접근 거부 |
| PostgreSQL | jhworks_demo_runtime | demo schema USAGE, migration이 만드는 테이블 DML·sequence USAGE/SELECT, DDL·역할 승격 불가 |
| GCP SA | jhworks-demo-runtime | demo runtime DB/session Secret의 승인된 고정 version만; 서비스와 maintenance가 사용 |
| GCP SA | jhworks-demo-migrate | demo migration DB/session Secret의 승인된 고정 version만; migration Job이 사용 |
| GCP Secret | jhworks-demo-runtime-database | 새 DB runtime 역할 접속 정보 |
| GCP Secret | jhworks-demo-migration-database | 새 DB migration 역할 접속 정보 |
| GCP Secret | jhworks-demo-session-secret | staging과 다른 무작위 서명키 |
| Cloud Run | jhworks-demo-migrate | 단일 migration Job, retry0/CPU1/512MiB/timeout300초, seed 없음 |

위 GCP 권한은 승인 후 [실제 분리 기반](demo-identity-foundation.md)에 적용·독립 검증했다.
이어 [credential 초기 설정](demo-credential-setup.md)에서 별도 승인/사용자 입력으로 v1 세 개와
실제 역할 인증을 확인했다. 계정 이름이나 manifest만으로 실제 IAM 최소 권한이 증명되지는 않는다.
기존 demo 서비스/maintenance는 새 참조로 업데이트할 계획이며 새 인터넷 접근은 포함하지 않는다.

## 구현과 안전장치

`deploy/cloud-run/supabase-demo-bootstrap.sql`은 단일 DO 문으로 원자 실행한다.
vector가 extensions에 미리 설치돼 있고 기존 private schema가 있어야 한다.
목표 schema/역할 중 하나라도 존재하면 덮거나 채택하지 않고 실패한다. PUBLIC 등을 통해 private
schema 접근이 가능하면 전체 bootstrap을 롤백한다. private ACL을 자동 수정해서 통과시키지 않는다.
두 역할은 NOLOGIN/NOINHERIT이며 superuser/create role/create DB/replication/bypass RLS 권한이 없다.
비밀번호·LOGIN 설정은 후속 사용자 직접 실행 절차와 실제 인증 검증 전까지 보류한다.
이 문장은 bootstrap 자체의 범위이며, 이후 실제 LOGIN 활성화 증거는 위 credential 문서를 따른다.
Data API exposed schema에 새 schema를 추가하지 않는다.

`app.ops.demo_isolation`은 전용 계정·세 Secret 이름만 받는 offline profile이다. 기존 리허설용
generator는 유지한다. 잘못된 staging 참조, 잘못된 service/host, max>1/concurrency>4,
mutable/다른 project/region 이미지를 거부한다. service·migration·maintenance dry-run manifest만
생성하며 IAM, Secret 값, SQL 실행, cloud API 호출을 수행하지 않는다.

```sh
cd apps/api
uv run --frozen python -m app.ops.demo_isolation \
  --settings ../../deploy/cloud-run/isolated-demo.example.json \
  --api-image '<검증된 같은 project/region의 API digest>' \
  --web-image '<검증된 같은 project/region의 web digest>' \
  --commit '<full SHA40>' --output-dir ../../artifacts/cloud-run/isolated-demo
```

placeholder는 실제 검토한 값으로 바꾼다. 버전 이름이 다르다고 실제 서명키의 값도 다른지는 알 수 없으므로,
후속 설정에서 독립 생성과 실제 상호 인증 거부를 확인해야 한다. 기존 초기 staging credential 도구는
빈 프로젝트만 허용하므로 이 작업에 재사용하거나 기존 guard를 해제하지 않는다.

## 검증 계약

- 일반 테스트: staging 계정/각 Secret 재사용 거부, runtime/migration 참조 분리,
  IAM check/AI off/max1/dry-run 유지, 서로 다른 키의 세션 HTTP 상호 거부.
- PostgreSQL: loopback의 전용 jhworks_test DB/user만 허용한다. bootstrap→제한 migration 역할로
  **실제 Alembic 전체 history**→runtime CRUD·새 sequence 사용을 검증한다. private SELECT/UPDATE,
  runtime CREATE/DROP/SET ROLE 승격 거부, anon/authenticated schema 접근 거부, 재실행·PUBLIC 누출
  시 원자 실패와 private sentinel 보존을 확인한다. fixture DDL/역할은 outer transaction으로 롤백한다.
- Alembic env는 제공된 SQLAlchemy connection을 사용하는 test 경계를 추가한다. 일반 CLI의
  engine/transaction 실행은 기존 경로 그대로다. 테스트가 table metadata 생성으로 migration을 대체하지 않는다.
- 원격 Supabase pooler 연결의 role search_path, 실제 인증·Secret IAM, 원격 migration과 데이터 보존,
  새 키로 서비스 간 인증 거부는 적용 후 별도 검증한다. CI의 superuser session에서 단순 SET ROLE만으로
  승격 거부를 주장하지 않고 runtime session identity로 검증한다.

로컬 Docker daemon이 실행 중이 아니므로 PostgreSQL 검증은 CI의 disposable pgvector/PG17에서 실행한다.
테스트를 건너뛴 로컬 결과를 PostgreSQL 통과로 표현하지 않는다. 최종 결과는 PR exact-head CI를 참조한다.
로컬 관련 23개(기존 manifest 포함)와 새 profile/서명키 11개 테스트가 통과했다. 전체 API는
449개 수집 중 PostgreSQL 23개 skip, 나머지 통과/exit0, Ruff 통과, strict mypy154 files 통과다.
기본 Windows 실행에서 TestClient가 멈춰 해당 작업의 두 프로세스만 종료하고 기존 검증된 PTY 실행
경로에서 전체 테스트를 완료했다. 원격 DB·실제 LLM을 사용하지 않았다.

## 실제 적용 gate와 다음 순서

1. 코드/SQL 리뷰·CI 통과 후 병합한다.
2. 실제 리소스·역할·Secret 충돌과 기존 상태를 읽어 확인한다. 추가 Secret/Job 비용과 최소 IAM/DB
   변경 범위를 제시하고 승인받은 뒤 bootstrap·자원 설정을 적용한다. 유료 DB나 공개 전환은 포함하지 않는다.
3. 별도 credential helper를 준비·검증하고 사용자 직접 입력으로 새 인증정보 설정을 완료한다.
   생성값은 채팅·argv·SQL 로그·Git에 남기지 않는다. 부분 실패 시 inspect 전 재실행하지 않는다.
4. 전용 migration 역할로 새 schema를 생성하고 private fingerprint·runtime DDL/다른 schema 거부,
   새 session key·guest 흐름을 실제 private HTTP로 검증한다. rollback은 원래 참조 복귀로 준비한다.
5. 이 증거까지 확보해야 공개 체크포인트 1 완료다. 이후 공용 합성 규정/일정, 정리 운영/실패 감지,
   최종 브라우저 QA, Hosting 공개/실제 domain E2E, 포트폴리오 연결 순서로 진행한다.

학습/면접: search_path가 권한 경계를 대신하지 못하는 이유, migration/runtime 역할을 나누는 이유,
서명키 분리와 DB 분리가 막는 서로 다른 실패, 별도 schema와 별도 DB의 장애 경계 차이를 설명한다.
