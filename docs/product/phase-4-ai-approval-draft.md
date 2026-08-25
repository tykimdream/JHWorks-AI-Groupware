# Phase 4 — AI Approval Draft

상태: **완료 (2026-08-25)**

## 1. 이번 단계의 목표

사용자의 짧은 자연어 요청을 JHWorks 전자결재 양식에 맞는 Structured Approval Draft로 변환한다. 정보가 부족하면 한 번에 답하기 쉬운 질문을 제시하고, 완성된 미리보기를 사용자가 명시적으로 확인한 뒤에만 실제 `DRAFT`를 저장한다.

대표 시나리오:

> 다음 주 화요일 부산 고객사 미팅 출장 결재 작성해줘.

## 2. 해결하는 문제

전자결재 작성자는 회사 양식의 모든 필드를 기억하고 자연어 업무 맥락을 제목, 본문, 일정, 관계처와 비용 내역으로 다시 나눠 입력해야 한다. 특히 출장 문서는 빠진 정보를 뒤늦게 발견해 결재자와 재소통하는 비용이 크다.

AI는 비정형 요청에서 의미를 추출하고 업무 문서 문장을 작성하는 데 사용한다. 필수 필드, 날짜 순서, 비용 합계, 지원 문서 유형, 권한, 저장과 중복 방지는 일반 코드가 담당한다.

## 3. User Scenario

1. 사용자가 `AI로 초안 만들기`에서 자연어 요청을 입력한다.
2. AI가 현재 지원하는 결재 유형과 구조화 필드 후보를 추출한다.
3. 서버가 JHWorks 양식 기준으로 필수 정보와 값의 일관성을 검사한다.
4. 정보가 부족하면 서버가 빠진 필드에 대응하는 질문을 반환한다.
5. 사용자는 일반 문장으로 추가 정보를 답하고 서버는 전체 요청을 다시 구조화한다.
6. 모든 필수 정보가 모이면 제목, 본문과 구조화 데이터를 미리보기로 보여준다.
7. 서버는 정책 검색 결과가 있으면 관련 규정 섹션을 함께 보여준다.
8. 사용자가 `Draft로 저장`을 명시적으로 누르면 미리보기와 결합된 confirmation token을 검증하고 정확히 한 개의 `DRAFT`를 만든다.
9. AI는 문서를 제출하거나 승인하지 않는다.

## 4. 설계

```text
natural-language request + follow-up answers
                    ↓
       OpenAI Structured Output
                    ↓
         untrusted draft candidate
                    ↓
 deterministic normalization / validation
       ├── missing → server questions
       ├── unsupported → future workflow 안내
       └── ready → policy retrieval + preview
                              ↓
                signed confirmation token
                              ↓ explicit confirm
                backend authorization
                              ↓
                 idempotent DRAFT create
```

LangGraph는 사용하지 않는다. 현재 workflow는 `질문 필요`, `미리보기 준비`, `지원하지 않는 요청`, `확정 완료`로 상태가 고정되어 있어 명시적인 application service가 더 작고 검증하기 쉽다.

대화 전문은 OpenAI에 저장하지 않도록 Responses API에 `store=False`를 사용한다. 서버는 현재 날짜와 `Asia/Seoul` timezone을 명시해 상대 날짜 해석의 기준을 고정한다.

## 5. 필요한 데이터

### 입력

- 최초 자연어 요청
- 사용자의 후속 답변 목록
- 현재 날짜와 timezone
- 현재 로그인 사용자 ID를 변환한 provider safety identifier

### AI가 반환하는 후보

- intent: `GENERAL`, `BUSINESS_TRIP`, `EXPENSE`, `LEAVE`, `UNSUPPORTED`
- 제목과 본문
- 총액
- 출장지, 기간, 관계처/행사, 방문 목적
- 교통비, 숙박비, 식비, 기타 비용

### 서버가 추가하는 데이터

- 상태: `NEEDS_INPUT`, `PREVIEW`, `UNSUPPORTED`
- 누락 field와 질문
- 정책 검색 상태와 인용
- provider/model/prompt version/token/latency metadata
- 사용자와 exact preview에 결합된 만료 가능한 confirmation token

## 6. 구현할 범위

- `GENERAL`, `BUSINESS_TRIP` 자연어 초안 준비
- 여러 번의 자연어 후속 답변
- Structured Output adapter와 provider 장애 경계
- 서버 결정적 누락/날짜/금액 검증
- 출장 정책 retrieval과 근거 표시
- exact preview hash, 사용자, 만료 시간에 결합된 confirmation token
- 확인 재시도에도 중복 생성하지 않는 idempotent Draft 저장
- AI 작성 전용 UI와 생성된 Draft 상세 화면 이동
- API, service, adapter와 핵심 사용자 흐름 테스트

## 7. 구현하지 않을 범위

- `EXPENSE`, `LEAVE` 문서 저장
- LLM Tool Calling
- 결재 자동 제출, 승인 또는 반려
- 외부 캘린더, 프로젝트 일정과 휴가 잔여일 조회
- 장기 대화 세션 저장과 범용 Chat UI
- 첨부 파일 업로드 또는 영수증 OCR

`EXPENSE`와 `LEAVE` intent는 조용히 다른 양식으로 바꾸지 않고 후속 Phase를 안내한다. 출장비 정산 요청을 출장 신청으로 잘못 저장하는 것보다 명확히 지원 범위를 알리는 편이 안전하다.

## 8. 기술적으로 새롭게 다루는 개념

- 자연어 extraction과 문서 generation의 Structured Output
- AI 결과를 신뢰하지 않는 deterministic post-validation
- 미리보기 데이터에 결합된 signed confirmation token
- side effect endpoint의 idempotency
- relative date grounding
- 생성 workflow에서의 RAG 재사용

## 9. 테스트

- 자연어 출장 요청이 structured candidate로 변환된다.
- 필수 정보가 빠지면 데이터는 저장되지 않고 정확한 질문이 반환된다.
- 후속 답변으로 필드가 채워지면 미리보기 상태가 된다.
- 날짜 역전과 비용 합계 불일치는 서버가 질문 상태로 되돌린다.
- Expense/Leave intent는 저장할 수 없다.
- 변조되거나 다른 사용자의 token, 만료된 token은 거부된다.
- 동일 confirmation을 재시도해도 Draft는 하나만 생성된다.
- provider 장애 시 기존 결재 기능과 데이터는 영향을 받지 않는다.
- frontend lint, type-check와 production build를 통과한다.

### Live evaluation

2026-08-25에 실제 OpenAI API와 local application으로 다음을 검증했다.

- 모델: `gpt-5.4-mini-2026-03-17`
- 최종 prompt version: `approval-draft-v3-related-party-mapping`
- extraction dataset: 5/5 통과
- 평가 intent: 향후 출장, 이미 사용한 경비, 휴가, 일반 결재
- multi-turn 평가: 후속 답변의 교통비·식비·총액과 행사명을 원 요청에 결합
- 실제 UI: 최초 요청 → 비용 추가 질문 → 날짜 추가 질문 → 정책 근거 미리보기 → Draft 저장
- 실제 생성 Draft: `apr_e7509ff8b2934287a58d8b31a9cb249f`
- 미리보기 검색: `TRAVEL-1`, `TRAVEL-2`, `TRAVEL-3`, `TRAVEL-4`
- 자동 검증: Ruff, mypy strict, pytest 40개, ESLint, TypeScript, Next.js production build
- fresh SQLite migration과 `source_confirmation_id` unique constraint 확인

초기 평가에서는 후속 답변의 비용 또는 행사명 mapping이 간헐적으로 누락되었다. 서버 누락 검사가 잘못된 저장을 차단했으며, 후속 답변 결합과 `행사명 → clientName` mapping을 prompt에 명시한 v3에서 5/5를 통과했다. 이 수치는 작은 synthetic dataset의 단일 실행 결과로 품질 보장을 의미하지 않는다.

## 10. 완료 조건

- 사용자가 짧은 요청과 후속 답변만으로 출장 또는 일반 결재 미리보기를 만들 수 있다.
- 미리보기 전과 명시적 확정 전에는 Approval row가 생성되지 않는다.
- 생성된 문서는 기존 수동 Draft와 동일한 편집·AI 검토·제출 흐름을 사용한다.
- AI와 일반 코드의 책임, 지원하지 않는 intent와 안전 경계가 문서화되어 있다.
- 자동 검증과 실제 OpenAI smoke test 결과가 기록되어 있다.

## 11. 다음 단계

Phase 5에서는 승인선, 현재 사용자, 정책 검색 같은 read-only 업무 기능을 좁은 Tool로 노출하고 backend authorization을 유지한다. 이후 Human-in-the-loop Agent workflow를 거쳐, 휴가 가능일 추천은 사내 행사·프로젝트 핵심 기간·팀 휴가 현황·휴가 규정을 결정적 계산으로 결합하는 독립 체크포인트로 구현한다.
