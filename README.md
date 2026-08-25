# JHWorks AI Groupware

AI-powered groupware and approval platform for the completely fictional company **JHWorks**.

JHWorks AI Groupware는 과거 회사의 제품이나 자산을 재현하지 않고, 일반적인 Enterprise workflow 문제를 바탕으로 처음부터 설계한 독립 프로젝트다. 모든 인물, 조직, 정책, 계정과 업무 데이터는 synthetic data다.

## Current Status

**Phase 1 — Minimal Groupware가 완료되었다.** AI를 연결하기 전에 권한과 상태가 정확한 기준 업무 시스템을 구축했다.

- demo 계정 로그인과 HttpOnly session cookie
- 직원, 부서, 직속 관리자 조회
- GENERAL/BUSINESS_TRIP 결재 Draft 작성·수정
- 작성자 제출, 직속 관리자 승인·반려
- 반려 문서 재작성과 제출 회차 이력
- 서버 Authorization, 상태 전이, optimistic concurrency
- version과 section ID를 가진 가상 정책 원문
- FastAPI integration test와 Next.js production build 검증

AI Review, RAG, Tool Calling과 Agent는 아직 구현하지 않았다. 기반 시스템이 안정된 뒤 phase별로 추가한다.

## Why This Problem

전자결재는 작성자가 목적, 일정, 금액, 세부 내역과 규정을 동시에 고려해야 한다. 정보가 모호하거나 빠지면 결재자가 문서를 반려하고 작성자와 다시 소통해야 한다.

일반 코드만으로 필수 field, 날짜, 금액과 권한은 정확하게 검증할 수 있다. 반면 업무 목적의 명확성, 의미상 누락, 자연어 요청의 구조화와 정책 문서의 관련 section 탐색은 LLM/RAG가 도움을 줄 수 있다. JHWorks AI Groupware는 두 책임을 분리하고 실제 데이터 변경은 사용자가 확인하도록 설계한다.

## Architecture

```text
Next.js web
    ↓ REST + HttpOnly cookie
FastAPI modular monolith
    ├── Authentication / Organization
    ├── Approval domain + Authorization
    ├── Company Policy
    └── SQLAlchemy + Alembic
              ↓
          PostgreSQL
```

Repository structure:

```text
apps/
├── api/   # FastAPI, domain/service, SQLAlchemy, migration, tests
└── web/   # Next.js App Router, TypeScript, minimal workflow UI
docs/
├── product/
├── code-conventions.md
CONTRIBUTING.md
```

## Approval Workflow

```text
DRAFT ──submit──> PENDING ──approve──> APPROVED
                      └────reject───> REJECTED ──revise──> DRAFT
```

- 상태를 임의로 PATCH하지 않고 submit/approve/reject/revise command를 사용한다.
- 제출 시 backend가 작성자의 현재 manager를 결재자로 계산한다.
- 반려 후 재상신은 새 ApprovalLine round를 생성해 과거 결정을 보존한다.
- 수정과 command는 문서 version을 비교해 오래된 화면의 덮어쓰기를 막는다.

## Demo Accounts

공통 비밀번호: `demo1234`

| 역할 | 이메일 | 가능한 작업 |
| --- | --- | --- |
| 작성자 윤서진 | `seojin.yoon@jhworks.test` | Draft 작성·제출·재작성 |
| 결재자 최도윤 | `doyun.choi@jhworks.test` | Sales 문서 승인·반려 |
| 정책 운영 한가람 | `garam.han@jhworks.test` | 가상 정책 조회 |

이 계정은 local portfolio demo 전용이며 실제 인증 시스템을 나타내지 않는다.

## Run with Docker

Requirements: Docker Engine과 Docker Compose v2 plugin

```bash
cp .env.example .env
docker compose up --build
```

- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`

API container가 migration과 idempotent seed를 실행한 뒤 시작한다.

## Local Development

Requirements: Node.js 24+, pnpm 10+, Python 3.12+, uv

```bash
pnpm install
uv sync --project apps/api
pnpm db:migrate
pnpm db:seed
```

두 terminal에서 실행한다.

```bash
pnpm dev:api
pnpm dev:web
```

기본 local database는 SQLite다. PostgreSQL과 동일한 환경은 Docker Compose를 사용한다.

## Validation

```bash
pnpm validate
```

이 명령은 backend lint/type-check/test와 frontend lint/type-check/production build를 실행한다.

## Security Boundary

- LLM과 Agent는 현재 존재하지 않으며, 이후에도 security boundary로 취급하지 않는다.
- backend service가 작성자와 지정 결재자를 검증한다.
- UI에서 action을 숨겨도 backend 검증은 생략하지 않는다.
- 실제 업무 실행용 idempotency와 confirmation token은 Agent phase에서 추가한다.
- 현재 demo auth는 local 실행용이다. Production에는 secret manager, secure cookie, CSRF 대응, account lifecycle과 SSO 검토가 필요하다.

## Technical Decisions

- **Modular monolith**: 현재 규모에서 microservice 운영 비용 없이 명확한 Tool/service 경계를 만든다.
- **Command endpoint**: 범용 status 수정 대신 업무 의도와 권한을 endpoint별로 강제한다.
- **Optimistic concurrency**: 장시간 DB lock 없이 오래된 UI와 AI 결과의 덮어쓰기를 방지한다.
- **Structured policy sections**: RAG 이전부터 `policyId + version + sectionId`를 안정적인 근거 식별자로 사용한다.
- **No LangGraph yet**: Phase 1에는 중단·재개가 필요한 Agent workflow가 없으므로 도입하지 않는다.

상세 결정은 [Phase 0 제품·도메인 정의](docs/product/phase-0-product-domain-definition.md)와 [Phase 1 설계](docs/product/phase-1-minimal-groupware.md)에 기록한다.

## Roadmap

1. Phase 1 — Minimal Groupware
2. Phase 2 — Structured AI Approval Review
3. Phase 3 — Policy RAG
4. Phase 4 — AI Approval Draft
5. Phase 5~6 — Tool Calling, Agent workflow, Human-in-the-loop
6. Phase 7~8 — Leave and Expense Agent
7. Phase 9~11 — Evaluation, Guardrail, Observability, Deployment, Portfolio

## Contributing

[기여 가이드](CONTRIBUTING.md), [코드 컨벤션](docs/code-conventions.md), [PR 템플릿](.github/pull_request_template.md)을 따른다.
