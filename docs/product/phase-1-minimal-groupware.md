# Phase 1 — Minimal Groupware

상태: **완료 (2026-08-21)**

## 1. 이번 단계의 목표

AI 없이도 정확하게 동작하는 JHWorks의 최소 업무 시스템을 만든다. 사용자는 로그인하고 출장 결재 Draft를 작성·수정·제출할 수 있으며, 서버가 계산한 직속 관리자는 해당 문서를 승인하거나 반려할 수 있어야 한다.

## 2. 해결하는 문제

AI가 연결될 실제 application boundary가 없으면 이후 단계의 Tool Calling과 Authorization은 mock 함수에 머물게 된다. Phase 1은 LLM이 없어도 상태, 권한, 데이터 무결성이 보장되는 기준 시스템을 제공한다.

## 3. User Scenario

1. 윤서진이 demo 계정으로 로그인한다.
2. 자신의 부서와 직속 관리자를 확인한다.
3. 부산 고객사 방문 출장 Draft를 작성하고 저장한다.
4. 내용을 확인한 뒤 제출한다.
5. 직속 관리자 최도윤이 로그인해 배정된 문서를 조회한다.
6. 관리자가 승인하거나 사유와 함께 반려한다.
7. 반려된 경우 윤서진이 문서를 Draft로 되돌려 수정할 수 있다.

## 4. 설계

### Architecture

```text
Browser
  └── Next.js web (apps/web)
        └── REST + HttpOnly session cookie
              └── FastAPI modular monolith (apps/api)
                    ├── Auth / Employee / Organization
                    ├── Approval domain + authorization
                    ├── Company Policy seed data
                    └── SQLAlchemy
                          └── PostgreSQL
```

- 하나의 저장소에 `apps/web`, `apps/api`를 두는 monorepo로 구성한다.
- backend는 배포 단위 하나인 modular monolith로 시작한다.
- route는 HTTP 변환, service는 use case와 권한, domain은 상태 전이를 담당한다.
- DB model을 API response로 직접 노출하지 않고 Pydantic schema로 계약을 정의한다.
- frontend는 REST 계약을 사용하는 얇은 업무 UI로 만들고 시각 효과보다 상태와 오류 표현에 집중한다.

### Authentication과 Authorization

- 가상 계정의 email/password로 로그인하고 backend가 서명한 JWT를 HttpOnly cookie로 발급한다.
- cookie의 identity는 인증 수단이며 모든 resource 접근 권한은 service에서 다시 확인한다.
- Phase 1은 portfolio용 local demo auth다. password hashing, 계정 관리, refresh token, SSO는 후속 Production 범위다.
- frontend에서 버튼을 숨기는 것과 무관하게 backend가 작성자·결재자 권한을 강제한다.

### 상태 전이

```text
DRAFT -> PENDING -> APPROVED
                 -> REJECTED -> DRAFT
```

- 상태를 직접 PATCH하지 않고 `submit`, `approve`, `reject`, `revise` command endpoint를 사용한다.
- 제출 시 서버가 작성자의 현재 `managerId`로 ApprovalLine을 생성한다.
- 반려 뒤 재상신하면 새 `round`의 ApprovalLine을 생성해 과거 결정을 보존한다.
- `version`이 일치하지 않으면 `409 Conflict`로 오래된 수정을 막는다.

### API Surface

| Method | Path | 목적 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | demo 로그인과 session cookie 발급 |
| `POST` | `/api/v1/auth/logout` | session 제거 |
| `GET` | `/api/v1/employees/me` | 현재 사용자와 관리자 조회 |
| `GET` | `/api/v1/departments` | 조직 조회 |
| `GET` | `/api/v1/approvals` | 접근 가능한 결재 목록 조회 |
| `POST` | `/api/v1/approvals` | Draft 생성 |
| `GET` | `/api/v1/approvals/{id}` | 권한이 있는 결재 상세 조회 |
| `PATCH` | `/api/v1/approvals/{id}` | 작성자의 Draft 수정 |
| `POST` | `/api/v1/approvals/{id}/submit` | 작성자의 Draft 제출 |
| `POST` | `/api/v1/approvals/{id}/approve` | 지정 관리자의 승인 |
| `POST` | `/api/v1/approvals/{id}/reject` | 지정 관리자의 반려 |
| `POST` | `/api/v1/approvals/{id}/revise` | 작성자가 반려 문서를 Draft로 전환 |
| `GET` | `/api/v1/policies` | 활성 가상 정책 원문 조회 |

## 5. 필요한 데이터

- 가상 Department 4개: Executive, Sales, Engineering, Corporate Operations
- 가상 Employee 7명: CEO, 부서 관리자, 일반 직원
- demo login credential: public README에 공개 가능한 프로젝트 전용 계정
- 가상 정책: 출장, 경비, 휴가 정책 각각 version과 안정적인 section ID 포함
- Approval 및 ApprovalLine: 사용자 동작으로 생성

실제 사람, 실제 회사 email domain, 실제 사내 규정을 사용하지 않는다.

## 6. 구현할 범위

- PostgreSQL schema와 migration
- synthetic seed command
- cookie 기반 demo login/logout
- 현재 직원·부서·관리자 조회
- GENERAL/BUSINESS_TRIP Draft CRUD 중 필요한 최소 동작
- 목록·상세·제출·승인·반려·재작성
- 상태 전이, authorization, optimistic concurrency
- 구조화 로그의 request ID
- backend unit/integration test
- frontend login, 목록, 작성, 상세 및 결재 action UI
- Docker Compose와 local 실행 문서

## 7. 구현하지 않을 범위

- AI Review, LLM API, RAG, embedding, LangGraph, Tool Calling
- 회원가입, password 변경, refresh token, SSO
- 정책 관리 UI와 실제 첨부파일 업로드
- 복잡한 결재선, 알림, pagination 최적화
- Cloud infrastructure와 production secret manager

## 8. 기술적으로 새롭게 배워야 할 개념

### Modular Monolith

- What: 하나의 배포 단위 안에서 도메인별 module boundary를 유지하는 구조다.
- Why: 현재 규모에서 분산 시스템 비용 없이 향후 Agent tool이 호출할 명확한 service를 제공한다.
- Alternative: 단순 CRUD 단일 파일 또는 microservice가 있다.
- Trade-off: module boundary를 코드 리뷰로 지켜야 하지만 network transaction과 운영 복잡성이 없다.
- Production: module 간 직접 DB 접근이 늘지 않도록 service boundary와 의존 방향을 관리해야 한다.

### Optimistic Concurrency

- What: 수정 시 읽었던 `version`을 보내 현재 version과 비교하는 방식이다.
- Why: 사용자가 오래 열어 둔 화면이나 늦게 도착한 AI 결과가 최신 문서를 덮어쓰는 일을 막는다.
- Alternative: pessimistic DB lock이 있다.
- Trade-off: 충돌 시 사용자가 다시 읽고 변경을 재적용해야 하지만 장시간 lock을 잡지 않는다.
- Production: 충돌 응답과 UI 재시도 경험을 명확하게 설계해야 한다.

### Command Endpoint

- What: 상태 값을 임의로 수정하는 대신 `submit`, `approve`처럼 업무 의도를 API로 표현한다.
- Why: 권한, 선행 조건, audit를 command별로 강제할 수 있다.
- Alternative: 범용 `PATCH { status }`가 있다.
- Trade-off: endpoint 수가 늘지만 허용되지 않은 상태 변경을 차단하기 쉽다.
- Production: retry와 중복 실행에 대비해 Agent 단계에서 idempotency를 추가한다.

## 9. 구현

다음 순서로 수직 slice를 만든다.

1. 저장소와 실행 환경
2. domain model과 migration
3. auth와 current employee
4. Draft 생성·조회·수정
5. 제출·승인·반려·재작성
6. frontend 사용자 흐름
7. seed, 문서, Docker

## 10. 테스트

- domain test: 허용·금지 상태 전이
- service test: 작성자/결재자 authorization, manager 계산, version 충돌
- API integration test: 로그인부터 승인/반려까지
- 실패 test: 타인 수정, 잘못된 관리자 승인, 반려 사유 누락, 관리자 없음, 중복 처리
- frontend: lint, type-check, production build
- manual smoke test: 두 demo 계정으로 작성자와 결재자 흐름 확인

## 11. 완료 조건

[Phase 0의 MVP 완료 기준](phase-0-product-domain-definition.md#7-mvp-완료-기준)을 모두 충족하고, 새 환경에서 문서의 명령만으로 DB·API·web을 실행할 수 있어야 한다.

## 12. 다음 단계

Phase 1 완료 후에만 Phase 2 AI Approval Review로 이동한다. Phase 2는 RAG와 Agent 없이 단일 structured LLM call로 문서 누락과 표현 품질을 검토하는 데 집중한다.

검증 결과:

- backend lint와 strict type-check 통과
- 14개 API/domain integration test 통과
- frontend lint, type-check, production build 통과
- PostgreSQL 17에서 migration, synthetic seed, health, demo login 확인
- 로컬 브라우저에서 작성자 Draft 생성·제출 → 결재자 조회·승인 흐름 확인
- API와 web container image build 확인
