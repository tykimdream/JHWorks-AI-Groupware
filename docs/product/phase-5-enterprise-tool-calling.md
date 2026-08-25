# Phase 5 — Read-only Enterprise Tool Calling

상태: **완료 (2026-08-25)**

## 1. 이번 단계의 목표

AI가 JHWorks의 실제 application service를 좁은 function tool로 호출해 현재 사용자, 직속 관리자, 내 결재 현황과 사내 정책을 조회할 수 있게 한다. LLM은 DB에 직접 접근하지 않으며, 이번 단계의 Tool은 모두 읽기 전용이다.

## 2. 해결하는 문제

LLM만으로는 사용자의 실제 조직, 결재 상태, 휴가 잔여일과 회사 정책을 알 수 없다. 모든 데이터를 prompt에 미리 넣으면 과도한 정보 노출과 비용이 생긴다. 필요한 데이터만 해당 사용자의 권한으로 조회하는 좁은 Tool 경계가 필요하다.

## 3. User Scenario

- `내 직속 관리자가 누구야?`
- `내가 올린 결재 중 대기 중인 것 보여줘.`
- `남은 연차가 며칠이야?`
- `출장 숙박비 규정 알려줘.`

AI는 요청에 필요한 Tool만 선택한다. 사용자는 최종 답변과 실제 실행된 Tool, 정책 원문 인용을 함께 확인한다.

## 4. Tool 계약

| Tool | 입력 | 서버 권한 범위 | 출력 |
| --- | --- | --- | --- |
| `get_current_employee` | 없음 | 현재 session 사용자만 | 기본 프로필, 부서, 잔여 연차 |
| `get_my_manager` | 없음 | 현재 사용자의 manager만 | 이름, 직급, 부서 |
| `list_my_approvals` | status, limit | author가 현재 사용자와 같은 문서만 | 상태, 제목, 금액, 갱신일 |
| `search_company_policy` | query, policyType, topK | 현재 active/effective synthetic 정책 | stable citation과 원문 |

임의의 `employeeId`나 SQL, URL을 Tool 인자로 받지 않는다. 다른 직원 또는 전체 조직을 조회하는 범용 Tool은 만들지 않는다.

## 5. Workflow

```text
user message
    ↓
OpenAI Responses API + strict function schemas
    ↓ function call
server tool allowlist + Pydantic argument validation
    ↓
application service + backend authorization
    ↓ function_call_output (untrusted reference data)
OpenAI final Korean answer
    ↓
answer + executed tool audit + exact policy citations
```

- 최대 3회의 provider round와 최대 4회의 Tool 실행으로 제한한다.
- `parallel_tool_calls=false`로 실행 순서를 단순화한다.
- unknown Tool, 잘못된 argument와 한도 초과는 안전하게 실패한다.
- Tool 결과 안의 문자열은 prompt 명령이 아니라 untrusted data다.
- Responses API 요청은 `store=false`다.

## 6. 일반 코드와 LLM의 책임

| 영역 | 일반 코드 | LLM |
| --- | --- | --- |
| 사용자 식별 | HttpOnly session과 backend dependency | 사용자 ID를 선택하지 않음 |
| Tool 허용 | 이름 allowlist, strict argument schema, call/round limit | 필요한 읽기 Tool 선택 |
| 데이터 접근 | actor 범위 query, active policy filter | DB/SQL 직접 접근 금지 |
| 정확한 계산 | leave balance와 문서 수를 DB 값으로 반환 | 숫자를 추측하지 않음 |
| 정책 근거 | retrieval 결과의 stable citation과 원문 제공 | 제공된 결과를 한국어로 설명 |
| 데이터 변경 | 쓰기 Tool이 존재하지 않음 | 저장·제출·승인할 수 없음 |

## 7. 실패 처리와 관측성

- API key/provider 장애: `503 WORK_ASSISTANT_UNAVAILABLE`
- policy index 미준비/embedding 장애: Tool output에 retrieval 상태를 명시
- manager 없음: 정상 Tool 결과로 `manager=null`
- 잘못된 Tool/argument: provider boundary를 실패시키고 실행하지 않음
- round/call 한도 초과: 명시적 service unavailable 오류
- log: actor ID, tool 이름, round, latency, token usage만 기록하고 원문 query와 Tool 원문은 기록하지 않음

## 8. 구현 범위

- 단일 요청형 업무 조회 Assistant API와 UI
- OpenAI strict function calling adapter
- 읽기 전용 Tool registry와 application executor
- Tool 실행 audit와 정책 citation 표시
- fake provider/embedding 기반 권한·routing·실패 테스트
- 실제 모델 smoke test

## 9. 제외 범위

- Draft 생성·제출·승인·반려 Tool
- 장기 conversation 저장과 `previous_response_id`
- Agent가 선택한 임의 직원 조회
- 휴가 가능일 계산에 필요한 행사·프로젝트·팀 휴가 데이터
- LangGraph, background job과 multi-agent

## 10. 완료 조건

- AI가 최소 4개의 읽기 전용 Tool 중 필요한 Tool을 호출한다.
- Tool argument가 strict schema와 서버 Pydantic schema를 모두 통과한다.
- 모든 업무 데이터는 현재 actor의 application 권한으로 조회된다.
- 응답이 실행된 Tool과 정책 citation을 노출한다.
- 어떤 요청도 업무 데이터를 변경할 수 없다.
- routing, 권한, unknown Tool, provider 실패와 call limit을 자동 검증한다.

### Live evaluation

2026-08-25에 실제 OpenAI API, local SQLite와 정책 인덱스로 다음을 검증했다.

- 모델: `gpt-5.4-mini-2026-03-17`
- prompt version: `work-assistant-v3-plain-answer`
- Tool routing dataset: 5/5 통과
- `get_current_employee`: 잔여 연차 9.5일, 2 rounds, 1,465 tokens
- `get_my_manager`: 현재 actor의 직속 관리자 조회, 2 rounds, 1,443 tokens
- `list_my_approvals`: `status=null`, `limit=5`, actor 소유 문서만 조회
- 출장 숙박비: `policyType=TRAVEL`, `TRAVEL-1` 검색
- 사용 완료 경비 영수증: `policyType=EXPENSE`, `EXPENSE-2` 검색
- 실제 브라우저: 답변, 실행 Tool audit, 인자·서버 결과와 정책 원문 렌더링 확인
- 자동 검증: Ruff, mypy strict, pytest 48개, ESLint, TypeScript, Next.js production build

초기 smoke test에서는 출장 숙박비 질문을 `EXPENSE`로 라우팅했지만, 제공된 정책 밖의 한도를 단정하지 않고 검증 실패를 표시했다. 정책 domain mapping을 prompt에 명시한 뒤 같은 질문을 `TRAVEL`로 라우팅해 1박 120,000원과 `policy_travel:1.0:TRAVEL-1`을 정확히 반환했고, 최종 dataset 5/5를 통과했다. 이 수치는 작은 synthetic dataset의 단일 실행 결과로 품질 보장을 의미하지 않는다.

## 11. 다음 단계

Phase 6에서는 휴가 추천보다 먼저 연도별 휴가 계정과 회사 행사·프로젝트 핵심 기간·팀 휴가를 application domain으로 구축한다. 이후 이 데이터를 좁은 읽기 Tool로 제공하고, 결정적 availability engine이 후보 날짜를 계산한다. 휴가 결재 쓰기 Tool은 해당 결재 domain과 preview, explicit confirmation, idempotency, stale-state 검증이 준비된 뒤 추가한다.
