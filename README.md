# JHWorks AI Groupware

AI-powered groupware and approval platform for the completely fictional company **JHWorks**.

JHWorks AI Groupware는 과거 회사의 제품이나 자산을 재현하지 않고, 일반적인 Enterprise workflow 문제를 바탕으로 처음부터 설계한 독립 프로젝트다. 모든 인물, 조직, 정책, 계정과 업무 데이터는 synthetic data다.

## Current Status

**Phase 8 — Grounded Leave AI Assistant까지 완료했다.** 근태·휴가를 정식 도메인으로 만들고, 자연어 휴가 질문을 실제 날짜로 구조화한 뒤 결정적 가능일과 활성 정책 근거를 설명한다.

- demo 계정 로그인과 HttpOnly session cookie
- 직원, 부서, 직속 관리자 조회
- GENERAL/BUSINESS_TRIP/LEAVE 결재 Draft 작성·수정
- 작성자 제출, 직속 관리자 승인·반려
- 반려 문서 재작성과 제출 회차 이력
- 서버 Authorization, 상태 전이, optimistic concurrency
- version과 section ID를 가진 가상 정책 원문
- FastAPI integration test와 Next.js production build 검증
- 작성자 전용 `AI로 검토하기`와 Structured Output
- 일반 코드의 필수 field·날짜·금액 검사와 LLM 의미 검토 분리
- 문서 품질 issue, 서버 계산 점수와 편집·즉시 반영 가능한 AI 수정 예시
- 문서 version 기반 stale 결과 차단
- model, prompt version, latency와 token usage 추적
- OpenAI embedding과 PostgreSQL `pgvector` 기반 정책 section 검색
- `policyId + version + sectionId`가 포함된 검증 가능한 정책 인용
- 숙박비 한도와 증빙처럼 계산 가능한 정책 rule의 결정적 검사
- 허위 citation, 추측성 risk와 중복 issue의 서버 후처리
- `READY`, `NOT_APPLICABLE`, `NOT_INDEXED`, `UNAVAILABLE` 검색 상태 표시
- 자연어 일반/출장 결재 intent 분류와 Structured Approval Draft 생성
- 누락된 출장 기간·관계처·목적·비용을 위한 여러 번의 후속 질문
- 상대 날짜를 현재 날짜와 `Asia/Seoul` 기준으로 구조화
- 저장 전 정책 근거가 포함된 exact preview와 명시적 사용자 확인
- 사용자·preview hash·만료 시간에 결합된 signed confirmation token
- 같은 confirmation 재시도에도 하나의 Draft만 만드는 idempotent 저장
- 이미 사용한 비용과 휴가 요청을 잘못된 양식으로 저장하지 않는 unsupported intent 경계
- `get_current_employee`, `get_my_manager`, `list_my_approvals`, `search_company_policy` 읽기 Tool
- OpenAI strict function schema와 서버 Pydantic argument 이중 검증
- 임의 직원 ID를 받지 않는 actor-scoped 조직·결재 조회
- 최대 3 provider rounds, 최대 4 Tool calls와 unknown Tool 차단
- 최종 답변과 실행 Tool audit, 입력 인자, 서버 결과, 정책 citation 표시
- 연도별 휴가 부여·이월·사용·대기·가용 일수 계정
- 전사 행사·공휴일·부서 프로젝트 일정·팀 휴가를 구분한 근태 캘린더
- 현재 부서 일정과 같은 팀 휴가만 반환하는 `/attendance/overview` 권한 경계
- 주말·확정 휴무일을 제외한 서버 기준 휴가 차감 일수 계산
- 휴가 제출 시 예약, 승인 시 사용 확정, 반려 시 복원되는 원자적 상태 전이
- 휴가 결재와 캘린더 이벤트의 1:1 연결 및 사유 비공개 경계
- 잔여 연차·주말·휴무일·회사 행사·프로젝트·팀 휴가를 결합한 `/attendance/leave-availability`
- 가능·주의·제외 날짜 근거와 충돌 없는 후보 우선 정렬
- 추천 후보에서 휴가 전자결재 날짜·유형을 자동 입력하는 사용자 흐름
- `Asia/Seoul` 기준 자연어 날짜·탐색 범위·희망 일수 Structured Output
- 여러 round 후속 질문과 실제 날짜가 명시된 읽기 전용 휴가 상담
- 활성 휴가 정책 RAG와 결정적 availability 결과를 분리한 grounded 설명
- 휴일·프로젝트·잔여 부족·prompt injection에서도 서버 reason code를 유지하는 경계
- 휴가 상담 provider/model/prompt version/usage/latency 관측성

휴가 쓰기 Tool과 범용 Agent workflow는 아직 구현하지 않았다. 휴가 상담은 읽기 전용이며 사용자의 명시적 확인 없이 데이터를 저장하거나 문서를 제출하지 않는다.

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
    ├── Company Policy + structured policy rules
    ├── Deterministic review + OpenAI adapters
    ├── Policy retrieval + citation allowlist
    ├── Natural-language draft extraction + deterministic completeness checks
    ├── Signed preview confirmation + idempotent Draft creation
    ├── Read-only enterprise tool registry + actor-scoped executor
    ├── OpenAI function calling loop + tool execution audit
    ├── Attendance calendar + yearly leave account
    ├── Transactional leave approval workflow
    ├── Deterministic leave availability engine
    ├── Grounded leave request structuring + policy RAG explanation
    └── SQLAlchemy + Alembic
              ↓
      PostgreSQL + pgvector
```

AI Review는 관련 정책 section을 embedding search로 찾은 뒤 OpenAI Responses API와 Pydantic Structured Output으로 결과를 제한한다. AI Draft도 같은 Structured Output 경계를 사용하지만, 필수 field·날짜·비용 일관성은 서버가 다시 검사한다. 숫자 한도처럼 결정적인 정책 rule은 일반 코드가 계산한다. 고정된 workflow에는 아직 Agent framework를 사용하지 않는다.

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
# .env의 JHWORKS_OPENAI_API_KEY에 본인의 API key를 입력한다.
docker compose up --build
```

정책 RAG를 처음 사용할 때는 다른 terminal에서 active policy section을 한 번 색인한다.

```bash
docker compose exec api python -m app.scripts.index_policies
```

- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`

API container가 migration과 idempotent seed를 실행한 뒤 시작한다.

API key가 없어도 일반 결재 기능은 모두 사용할 수 있다. AI 기능은 각 기능별 안전한 `503`으로 실패하며 업무 데이터는 변경되지 않는다.

## Local Development

Requirements: Node.js 24+, pnpm 10+, Python 3.12+, uv

```bash
pnpm install
uv sync --project apps/api
pnpm db:migrate
pnpm db:seed
```

AI Review를 실행하려면 root `.env`에 다음 값을 설정한다.

```dotenv
JHWORKS_OPENAI_API_KEY=your-api-key
JHWORKS_OPENAI_MODEL=gpt-5.4-mini
JHWORKS_POLICY_EMBEDDING_MODEL=text-embedding-3-small
JHWORKS_APPROVAL_DRAFT_CONFIRMATION_TTL_MINUTES=15
```

`.env`는 Git에 포함하지 않는다. API key는 browser에 전달되지 않고 FastAPI에서만 사용한다.

최초 1회 또는 정책 내용·embedding model 변경 후 정책 인덱스를 갱신한다. 변경되지 않은 section은 다시 호출하지 않는다.

```bash
pnpm policy:index
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

실제 모델을 사용하는 명시적 AI 평가 명령은 기본 검증과 분리되어 있다. 실행 시 API 비용이 발생한다.

```bash
pnpm eval:ai-review
pnpm eval:policy-rag
pnpm eval:approval-draft
pnpm eval:work-assistant
pnpm eval:leave-assistant
```

## Security Boundary

- LLM은 문서 의미와 표현만 검토하며 security boundary로 취급하지 않는다.
- 검색된 policy section은 명령이 아닌 untrusted reference data로 취급한다.
- 정책 issue는 검색 결과에 존재하는 citation key만 허용하고 원문 인용은 DB에서 구성한다.
- backend service가 작성자와 지정 결재자를 검증한다.
- UI에서 action을 숨겨도 backend 검증은 생략하지 않는다.
- 제출·휴가 신청 같은 추가 실행 Tool의 idempotency와 confirmation 계약은 Agent phase에서 확장한다.
- AI Draft는 exact preview hash, 현재 사용자와 만료 시간에 결합된 confirmation token을 검증한다.
- 같은 confirmation token을 재사용해도 unique confirmation ID로 기존 Draft를 반환한다.
- 업무 조회 Assistant에는 읽기 전용 allowlist Tool만 제공하고 arbitrary employee ID를 입력받지 않는다.
- LLM이 선택한 Tool 이름과 인자는 서버 registry와 Pydantic schema를 다시 통과해야 한다.
- 현재 demo auth는 local 실행용이다. Production에는 secret manager, secure cookie, CSRF 대응, account lifecycle과 SSO 검토가 필요하다.
- 휴가 상담 모델 schema에는 상태·차감·충돌·후보·citation·쓰기 명령이 없고, 서버 계산 결과만 사용자에게 설명한다.

## Technical Decisions

- **Modular monolith**: 현재 규모에서 microservice 운영 비용 없이 명확한 Tool/service 경계를 만든다.
- **Command endpoint**: 범용 status 수정 대신 업무 의도와 권한을 endpoint별로 강제한다.
- **Optimistic concurrency**: 장시간 DB lock 없이 오래된 UI와 AI 결과의 덮어쓰기를 방지한다.
- **Structured policy sections**: RAG 이전부터 `policyId + version + sectionId`를 안정적인 근거 식별자로 사용한다.
- **Local policy source of truth**: 정책 원본은 application DB에 두고 embedding만 함께 저장한다.
- **pgvector with SQLite fallback**: Production은 PostgreSQL cosine search, local/test의 작은 corpus는 application cosine search를 사용한다.
- **Structured policy rules**: 숫자 한도와 증빙 조건은 LLM이 아니라 policy metadata와 일반 코드가 계산한다.
- **Structured Output**: OpenAI Responses API와 Pydantic schema로 출력 형식을 제한하고 서버 domain validation을 다시 수행한다.
- **Preview before write**: 자연어 변환과 추가 질문 중에는 Approval row를 만들지 않고, 확정된 exact preview만 저장한다.
- **Unsupported intent is explicit**: 경비·휴가 요청을 현재 지원하는 일반/출장 양식으로 조용히 바꾸지 않는다.
- **Narrow read tools**: 현재 actor에 고정된 작은 조회 Tool만 노출하고 DB나 범용 API 접근권을 주지 않는다.
- **Attendance before recommendation**: AI가 날짜를 추측하지 않도록 연도별 휴가 계정과 전사·부서·팀 일정을 먼저 application domain으로 만든다.
- **Server-owned leave accounting**: 클라이언트가 보낸 차감 일수를 신뢰하지 않고 업무 캘린더로 다시 계산하며 결재와 휴가 계정을 함께 commit한다.
- **Deterministic availability**: 휴가 후보와 충돌 여부는 LLM이 아니라 actor 범위의 휴가 계정과 일정으로 계산하고 근거 코드를 함께 반환한다.
- **Grounded leave conversation**: LLM은 상대 날짜와 의도만 구조화하고 여러 번의 모호성 질문, 정책 allowlist와 결정적 계산은 서버가 담당한다.
- **No LangGraph yet**: 검색→검토가 고정된 단일 workflow이므로 Agent state machine을 도입하지 않는다.

상세 결정은 [Phase 0 제품·도메인 정의](docs/product/phase-0-product-domain-definition.md), [Phase 1 설계](docs/product/phase-1-minimal-groupware.md), [Phase 2 AI Review](docs/product/phase-2-ai-approval-review.md), [Phase 3 Policy RAG](docs/product/phase-3-policy-rag.md), [Phase 4 AI Approval Draft](docs/product/phase-4-ai-approval-draft.md), [Phase 5 Enterprise Tool Calling](docs/product/phase-5-enterprise-tool-calling.md), [Phase 6 Attendance and Leave](docs/product/phase-6-attendance-and-leave.md), [Phase 7 Leave AI Assistant](docs/product/phase-7-leave-ai-assistant.md)에 기록한다.

## Roadmap

1. Phase 1 — Minimal Groupware ✅
2. Phase 2 — Structured AI Approval Review ✅
3. Phase 3 — Policy RAG ✅
4. Phase 4 — AI Approval Draft ✅
5. Phase 5 — Read-only Enterprise Tool Calling ✅
6. Phase 6 — Attendance and Leave Workflow ✅
7. Phase 7 — Deterministic Leave Availability ✅
8. Phase 8 — Grounded Leave AI Assistant ✅
9. Phase 9 — Confirmed Leave Draft and Submit Tools
10. Phase 10~11 — Evaluation, Guardrail, Observability, Deployment, Portfolio

## Contributing

[기여 가이드](CONTRIBUTING.md), [코드 컨벤션](docs/code-conventions.md), [PR 템플릿](.github/pull_request_template.md)을 따른다.
