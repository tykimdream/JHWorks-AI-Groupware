# Phase 0 — Product / Domain Definition

상태: **확정 (2026-08-21)**

대상 회사: **JHWorks**

원칙: 모든 인물, 조직, 규정, 데이터, 화면, API, 업무 흐름은 이 프로젝트를 위해 새로 만든다.

## 1. Product Scope

JHWorks AI Groupware는 그룹웨어 전체가 아니라, AI가 기업 업무를 안전하게 보조하는 능력을 증명하기 위한 최소 업무 플랫폼이다. 제품의 중심은 문서 편집 UI가 아니라 **비정형 요청을 구조화하고, 사내 규정과 실제 업무 데이터에 연결하며, 데이터 변경을 통제하는 과정**이다.

### 반드시 포함

| 영역 | 최소 기능 | 포함 이유 |
| --- | --- | --- |
| 사용자 | 현재 사용자 식별, 직원·부서·직속 관리자 조회 | Tool Calling과 Authorization의 실제 데이터 기반 |
| 조직 | 단순한 부서 계층과 직원-관리자 관계 | 결재선 계산과 권한 검증에 필요 |
| 전자결재 | Draft 작성·수정, 목록·상세, 제출, 승인, 반려 | 모든 AI 기능이 연결될 핵심 업무 시스템 |
| 정책 | 완전히 가상인 출장·경비·휴가 정책과 version/section | RAG의 근거 문서이자 평가 가능한 정답 기준 |
| AI Review | 문서 누락·표현·위험·정책 위반 검토, 근거 표시, 수정안 제안 | 단일 LLM 호출부터 RAG까지 단계적으로 발전 가능 |
| AI Draft | 자연어 요청을 구조화된 결재 초안으로 변환하고 누락 정보 질문 | Structured Output과 대화형 요구사항 수집을 증명 |
| Agent | 직원·관리자·잔여 휴가·정책·결재 Tool 조합 | Enterprise data와 LLM의 연결을 증명 |
| 안전한 실행 | 변경 Preview, 명시적 확인, 서버 권한 재검증, idempotency | Human-in-the-loop와 Production 관점의 핵심 |
| 품질 운영 | 회귀 평가 데이터, 핵심 trace, latency/token/error 기록 | “동작한다”가 아닌 측정 가능한 AI 시스템을 증명 |

### 의도적으로 제외

| 제외 항목 | 제외 이유 |
| --- | --- |
| 급여, 채용, CRM, ERP, PMS, 메신저 | 핵심 AI workflow를 증명하지 않으면서 도메인만 확장함 |
| 복잡한 다단계·병렬·대리·합의 결재 | 단일 직속 관리자 결재로도 workflow와 권한을 충분히 증명 가능 |
| 조직/사용자/정책 관리용 Admin UI | 초기에는 seed data와 관리 script로 충분함 |
| 실제 기업 SSO, SCIM, HR 연동 | 외부 통합보다 Agent·RAG·안전성 학습이 우선 |
| 모바일 앱, Electron 앱, 실시간 알림 | 핵심 시나리오와 직접 관련이 없음 |
| OCR 영수증 인식과 실제 파일 저장 | 이미지 처리와 object storage는 후속 확장 범위 |
| 범용 사내 검색과 자유로운 SQL Tool | 범위가 넓고 정보 노출 및 prompt injection 위험이 큼 |
| 정책 자동 작성·자동 승인 | 정책의 정답성과 Human-in-the-loop 원칙을 약화함 |
| Microservice, queue, Redis | 현재 부하와 장애 격리 요구에는 modular monolith로 충분함 |
| 완전 자율 Agent | 업무 데이터 변경은 항상 사용자의 명시적 확인이 필요함 |

### 제품 경계

- 로그인한 JHWorks 직원만 자신의 권한 범위에서 사용한다.
- AI는 조언, 구조화, 검색, 실행 계획 생성을 담당하지만 최종 권한 주체가 아니다.
- AI가 실패해도 사용자는 일반 전자결재 흐름을 계속 사용할 수 있어야 한다.
- 외부 실제 회사 데이터나 서비스를 연결하지 않고 synthetic data만 사용한다.

## 2. Persona

모든 인물은 JHWorks를 위해 만든 가상의 사용자다.

### Persona A — 윤서진, Sales Account Executive

- 역할: 고객 미팅과 국내 출장이 잦은 일반 직원
- 목표: 규정을 일일이 찾아보지 않고 빠르게 결재 문서를 작성하고 싶다.
- 현재 어려움: 목적·일정·비용 상세·증빙 요건을 놓쳐 관리자에게 다시 요청받는다.
- 필요한 가치: 제출 전 누락과 규정 위험을 발견하고 자연어 요청에서 Draft를 만들 수 있어야 한다.
- 권한: 자신의 결재와 휴가 정보만 조회·작성·제출할 수 있다.

### Persona B — 최도윤, Sales Manager

- 역할: Sales 직원의 직속 관리자이자 결재자
- 목표: 짧은 시간 안에 결재 목적, 비용 근거, 정책 위반 여부를 판단하고 싶다.
- 현재 어려움: 내용이 모호하거나 비용 세부 내역이 없는 문서가 반복적으로 올라온다.
- 필요한 가치: 제출 전에 문서 품질이 개선되어 승인·반려에 필요한 왕복이 줄어야 한다.
- 권한: 자신에게 배정된 대기 결재만 승인·반려할 수 있고 다른 부서 문서는 열람할 수 없다.

### Persona C — 한가람, Corporate Operations Policy Owner

- 역할: 가상의 출장·경비·휴가 정책을 관리하고 AI 품질을 점검하는 운영 담당자
- 목표: AI가 활성 정책의 정확한 section을 인용하고 반복 실패를 추적할 수 있어야 한다.
- 현재 어려움: 일반 LLM 답변은 어떤 규정 version을 근거로 했는지 알기 어렵다.
- 필요한 가치: 정책 version, 검색 근거, 평가 결과, 실패 trace를 확인할 수 있어야 한다.
- MVP 권한: 정책 데이터와 평가 결과를 읽는다. 정책 편집 Admin UI는 제공하지 않는다.

## 3. 핵심 User Scenario

최종 Demo는 세 시나리오에 집중한다.

### Scenario 1 — 근거가 있는 출장 결재 AI Review

1. 윤서진이 2박 3일 고객사 방문 결재를 작성한다.
2. 예상 비용 550,000원만 적고 세부 내역과 증빙 계획은 누락한다.
3. `AI 검토`를 실행한다.
4. 시스템은 일반 필드 검증과 정책 검색을 수행한다.
5. AI는 비용 내역 누락, 숙박 한도 확인 필요, 사전 승인 및 증빙 요건을 정책 section과 함께 보여준다.
6. AI는 수정안을 제안하지만 원문을 자동 변경하지 않는다.
7. 사용자가 원하는 제안만 직접 반영하고 제출한다.

포트폴리오 가치: Structured Output, RAG grounding, hallucination 제어, 사용자 통제를 한 흐름에서 보여준다.

### Scenario 2 — 자연어 출장 요청에서 안전한 Draft 생성·제출

1. 윤서진이 “다음 주 화요일 부산 고객 미팅 출장 결재 만들어줘”라고 요청한다.
2. Agent는 복귀일, 비용, 고객사 방문 목적 등 필수 정보가 없음을 확인하고 질문한다.
3. 필요한 답을 받은 뒤 직원·관리자·정책 Tool을 조회한다.
4. Agent는 구조화된 결재 Draft와 적용 정책, 예정 결재자를 Preview한다.
5. 사용자가 수정하거나 `Draft 저장`을 명시적으로 확인한다.
6. 제출 시에는 내용과 결재자를 다시 Preview하고 별도의 확인 후 한 번만 실행한다.

포트폴리오 가치: multi-step state, Tool Calling, schema validation, Human-in-the-loop, idempotency를 보여준다.

### Scenario 3 — 휴가 가능 여부 확인 후 결재 생성

1. 사용자가 “다음 주 목요일과 금요일 연차 가능한지 확인하고 신청해줘”라고 요청한다.
2. Agent는 자연어 날짜를 구조화하고 사용자에게 실제 날짜를 확인시킨다.
3. Tool로 잔여 연차와 직속 관리자를 조회하고 RAG로 휴가 정책을 검색한다.
4. 일반 코드가 영업일, 차감 일수, 잔여 일수, 신청 기한을 계산한다.
5. Agent가 가능 여부와 근거, 생성할 결재 Draft를 Preview한다.
6. 사용자가 확인한 경우에만 Draft를 저장하고, 다시 확인한 경우에만 제출한다.

포트폴리오 가치: LLM과 결정적 계산의 책임 분리, 실제 데이터 조회, 정책 검색, 안전한 실행을 보여준다.

## 4. Domain Model

아래는 DB schema가 아니라 제품 수준의 최소 논리 모델이다. 저장 방식과 index는 Phase 1 기술 설계에서 결정한다.

### Employee

| 필드 | 타입/예시 | 규칙 |
| --- | --- | --- |
| `id` | string, `emp_jhw_001` | 불변 식별자 |
| `name` | string | 완전히 가상인 표시 이름 |
| `email` | string | 프로젝트 전용 가상 도메인 사용 |
| `departmentId` | string | 존재하는 Department 참조 |
| `position` | string | 표시용 직책 |
| `role` | `EMPLOYEE \| MANAGER \| POLICY_OWNER` | 시스템 권한의 최소 역할 |
| `managerId` | string 또는 null | 직속 관리자, CEO만 null 허용 |
| `hireDate` | date | 휴가 정책 계산의 입력 |
| `leaveBalance` | number | 0.5일 단위, Phase 1에서는 seed 값 |
| `isActive` | boolean | 비활성 사용자의 신규 업무 차단 |

결정: `managerId`를 Employee에 명시해 초기 결재선 계산을 단순하게 한다. Department의 책임자와 개인의 직속 관리자가 항상 같다는 가정을 피한다.

### Department

| 필드 | 타입/예시 | 규칙 |
| --- | --- | --- |
| `id` | string, `dept_sales` | 불변 식별자 |
| `name` | string | JHWorks의 가상 부서명 |
| `parentDepartmentId` | string 또는 null | 단순 조직 계층 |
| `managerEmployeeId` | string | 부서 책임자 표시와 조회용 |
| `isActive` | boolean | 폐쇄된 부서를 이력에서 보존 가능 |

결정: Phase 1은 최대 2단계 조직만 사용한다. 조직 이동 이력과 matrix organization은 제외한다.

### Approval

| 필드 | 타입/예시 | 규칙 |
| --- | --- | --- |
| `id` | string, `apr_001` | 불변 식별자 |
| `type` | `GENERAL \| BUSINESS_TRIP \| EXPENSE \| LEAVE` | 세부 data schema의 discriminator |
| `title` | string | 사람이 읽는 문서 제목 |
| `content` | string | 목적과 설명의 원문 |
| `authorId` | string | 작성자 Employee |
| `status` | `DRAFT \| PENDING \| APPROVED \| REJECTED` | 허용된 transition만 가능 |
| `amount` | integer 또는 null | 원 단위, 금액 없는 문서는 null |
| `details` | type별 object | 아래의 type별 structured field |
| `attachmentMetadata` | array | Phase 1은 이름·종류·존재 여부만, 실제 업로드 제외 |
| `version` | integer | 동시 수정과 오래된 AI 결과 적용 방지 |
| `submittedAt` | datetime 또는 null | UTC 저장 |
| `decidedAt` | datetime 또는 null | UTC 저장 |
| `createdAt`, `updatedAt` | datetime | 감사와 정렬에 필요 |

`details`는 optional field가 많은 하나의 object 대신 type별 구조를 사용한다.

| Approval type | 최소 details |
| --- | --- |
| `GENERAL` | 추가 필드 없음 |
| `BUSINESS_TRIP` | `destination`, `startDate`, `endDate`, `costBreakdown`, `clientName`, `visitPurpose` |
| `EXPENSE` | `expenseDate`, `category`, `attendeeCount`, `merchant`, `receiptAttached` |
| `LEAVE` | `startDate`, `endDate`, `leaveUnit`, `requestedDays` |

결정: 공통 `content`는 사람의 설명을 보존하고 `details`는 계산·정책 검증에 사용한다. LLM이 작성한 문장만 다시 해석해 금액이나 날짜를 결정하지 않는다.

### ApprovalLine

| 필드 | 타입/예시 | 규칙 |
| --- | --- | --- |
| `id` | string | 불변 식별자 |
| `approvalId` | string | Approval 참조 |
| `step` | integer | Phase 1은 항상 1 |
| `round` | integer | 반려 후 재상신을 구분하는 제출 회차 |
| `approverId` | string | 제출 시 author의 manager로 서버가 결정 |
| `status` | `WAITING \| PENDING \| APPROVED \| REJECTED` | Approval 상태와 함께 transaction으로 변경 |
| `comment` | string 또는 null | 승인 의견은 선택, 반려 사유는 필수 |
| `actedAt` | datetime 또는 null | 승인·반려 시점 |

결정: 클라이언트나 LLM이 보낸 `approverId`를 신뢰하지 않는다. 서버가 조직 관계에서 계산하고 Preview와 실제 실행 시점에 다시 확인한다.

### CompanyPolicy

| 필드 | 타입/예시 | 규칙 |
| --- | --- | --- |
| `id` | string, `policy_trip` | 정책 계열의 안정적인 식별자 |
| `type` | `TRAVEL \| EXPENSE \| LEAVE \| APPROVAL \| SECURITY` | 검색 filter와 평가 분류 |
| `title` | string | 가상 정책명 |
| `version` | string | AI 응답 근거 재현에 필요 |
| `status` | `DRAFT \| ACTIVE \| ARCHIVED` | ACTIVE version만 업무 판단에 사용 |
| `effectiveFrom` | date | 적용 정책 결정 기준 |
| `sections` | array | 안정적인 section ID, 제목, 본문으로 구성 |
| `contentHash` | string | ingestion 대상 version의 동일성 확인 |
| `createdAt`, `publishedAt` | datetime | 정책 생명주기 추적 |

결정: AI 인용은 파일명이나 vector chunk 번호가 아니라 `policyId + version + sectionId`를 사용한다. chunk는 retrieval 구현 세부사항이므로 사용자 근거 ID가 될 수 없다.

## 5. Approval Workflow

### 상태 전이

```text
DRAFT ──submit──> PENDING ──approve──> APPROVED
                      └────reject───> REJECTED

REJECTED ──revise──> DRAFT
```

### 전이별 규칙

| 동작 | 요청자 | 선행 조건 | 서버 동작 | 실패 예시 |
| --- | --- | --- | --- | --- |
| Draft 생성 | 로그인 직원 | active Employee | author를 현재 사용자로 고정 | 비활성 사용자 `403` |
| Draft 수정 | 작성자 | 상태가 DRAFT, version 일치 | 내용 저장, version 증가 | 다른 사용자 `403`, version 충돌 `409` |
| Submit | 작성자 | 필수 field 유효, active manager 존재 | 결재선 계산, Approval/Line을 PENDING으로 transaction 변경 | 누락 `422`, 관리자 없음 `409` |
| Approve | 지정 approver | Approval과 Line이 PENDING | 두 상태를 APPROVED로 transaction 변경 | 권한 없음 `403`, 중복 처리 `409` |
| Reject | 지정 approver | PENDING, 반려 사유 존재 | 두 상태를 REJECTED로 transaction 변경 | 사유 누락 `422` |
| Revise | 작성자 | REJECTED | 기존 결정 이력은 유지하고 문서를 DRAFT로 전환, version 증가 | 작성자 아님 `403` |

### 불변 조건

- 작성자와 결재자는 동일할 수 없다. manager가 없거나 자기 자신이면 제출을 막는다.
- APPROVED 문서와 결정 이력은 수정하지 않는다.
- PENDING 문서는 작성자가 수정할 수 없다.
- 하나의 Approval에는 동시에 하나의 PENDING ApprovalLine만 존재한다.
- 상태 변경은 API 입력의 목표 상태를 그대로 저장하지 않고 허용된 command와 현재 상태로 계산한다.
- 모든 쓰기는 인증된 사용자와 `requestId`를 기록한다.
- Agent를 통한 submit/approve/reject에는 Preview 내용과 결합된 단일 사용 confirmation 및 idempotency key가 필요하다.

### AI Review와 문서 version

AI Review 요청에는 Approval의 `version`을 포함한다. 결과가 돌아온 뒤 문서 version이 달라졌다면 결과를 참고용으로 표시하고 자동 적용할 수 없게 한다. AI 수정안은 별도 제안이며 사용자가 선택하기 전까지 Approval 원문을 변경하지 않는다.

## 6. AI가 필요한 지점

### Scenario별 책임 분리

| Scenario | 일반 코드 | LLM | RAG | Tool |
| --- | --- | --- | --- | --- |
| 출장 결재 Review | schema, 날짜 순서, 합계, attachment 존재, status/version, 권한 검사 | 목적 명확성, 의미상 누락, 표현 품질, 위험 설명, 수정안 | 활성 출장·경비·보안 정책 section 검색 | Phase 2 embedded review는 service 호출, Phase 3부터 `search_policy`와 필요 시 `get_approval` |
| 출장 Draft 생성·제출 | 날짜 확정, 금액 합계, 필수 field, 결재선, 상태 전이, confirmation/idempotency | 의도·entity 추출, 모호성 판단, 후속 질문, 문서 문장 생성 | 문서 type별 필수 요건과 한도 검색 | `get_current_employee`, `get_manager`, `search_policy`, `create_approval_draft`, `submit_approval` |
| 휴가 확인·신청 | 실제 날짜 변환 확인, 영업일·차감 일수·잔여 일수·신청 기한 계산, 권한 | 자연어 요청 이해, 누락 정보 질문, 결과 설명 | 활성 휴가 정책 검색 | `get_current_employee`, `get_leave_balance`, `get_manager`, `search_policy`, `create_approval_draft`, `submit_approval` |

### 경계 원칙

- **LLM은 확률적인 언어 계층**이다. 사용자의 표현을 이해하고 설명을 생성하지만 숫자, 권한, 상태를 확정하지 않는다.
- **Structured Output은 신뢰 경계가 아니다.** 형식이 맞아도 내용은 틀릴 수 있으므로 schema validation 뒤에 domain validation을 수행한다.
- **RAG는 정책 근거 제공 계층**이다. 검색 문서에 없는 규칙을 모델의 일반 지식으로 보충하지 않는다.
- **Tool은 좁은 application capability**다. DB나 범용 HTTP 접근을 제공하지 않고 호출할 때마다 Authorization을 수행한다.
- **Agent는 security boundary가 아니다.** 잘못된 tool과 인자를 선택해도 backend가 거절할 수 있어야 한다.

### 단계별 기술 선택

- Phase 2 AI Review는 workflow가 한 번의 입력→검토→출력으로 끝나므로 LangGraph 없이 단일 structured LLM call로 시작한다.
- Phase 3에서 policy retrieval을 앞에 추가해도 고정 pipeline으로 충분하다.
- Phase 4의 누락 정보 질문은 명시적인 conversation state로 관리한다.
- Phase 5~6에서 여러 Tool, 중단 후 사용자 확인, 재개가 필요해질 때 LangGraph 도입 여부를 결정한다.

이 선택은 Agent 기술 자체가 아니라 상태 보존, 분기, 중단·재개라는 실제 복잡성이 생겼을 때만 비용을 지불하기 위한 것이다.

## 7. MVP 완료 기준

여기서 MVP는 **Phase 1 — Minimal Groupware 완료 기준**이다. AI 기능은 Phase 2부터 추가한다.

### 기능 완료 조건

- 완전히 가상인 JHWorks seed data로 최소 3개 부서, 관리자 포함 6명 이상의 Employee가 존재한다.
- 사용자는 demo account로 로그인하거나 명시적으로 선택된 demo identity를 통해 현재 사용자로 식별된다.
- 직원, 부서, 직속 관리자를 조회할 수 있다.
- `GENERAL`과 `BUSINESS_TRIP` 결재 Draft를 생성·수정·조회할 수 있다.
- 작성자는 자신의 Draft를 제출할 수 있고 서버가 직속 관리자를 결재자로 결정한다.
- 결재자는 자신에게 배정된 PENDING 문서를 승인하거나 사유와 함께 반려할 수 있다.
- 작성자와 결재자는 자신의 권한 범위에 맞는 목록과 상세만 조회한다.
- 반려된 문서는 작성자가 수정 가능한 Draft로 되돌릴 수 있다.
- 가상 출장·경비·휴가 정책이 version과 section을 가진 원문 데이터로 존재하지만 vector embedding과 AI 검색은 아직 하지 않는다.

### 안전성과 정확성 완료 조건

- API가 작성자·결재자 권한을 서버에서 검사하며 다른 사용자의 직접 URL/API 접근을 `403`으로 막는다.
- 잘못된 상태 전이와 중복 승인·반려를 `409`로 막는다.
- 필수 field, 날짜 순서, 원화 정수 금액을 schema/domain validation으로 검증한다.
- 동시 수정은 `version`으로 감지한다.
- 제출과 승인·반려는 transaction으로 처리되어 Approval과 ApprovalLine 상태가 어긋나지 않는다.
- 로그에 비밀정보와 불필요한 개인정보를 남기지 않고 `requestId`, actor, action, target, result를 추적할 수 있다.

### 테스트 완료 조건

- 정상 Draft→Submit→Approve와 Draft→Submit→Reject→Revise 흐름을 integration test로 검증한다.
- 다른 직원의 Draft 수정, 다른 관리자의 승인, 비활성 사용자, 관리자 없음, 중복 처리, version 충돌을 실패 테스트로 검증한다.
- 핵심 사용자 흐름을 frontend에서 수동으로 재현할 수 있고 PR에 실행 절차와 결과를 남긴다.

### 문서 완료 조건

- 실행 방법, 가상 계정, 상태 전이, 권한 matrix, API 계약이 문서화되어 있다.
- 모든 데이터가 synthetic임을 README와 seed data에 명시한다.
- Phase 1에서 내린 구조적 결정과 제외 범위를 ADR 또는 phase 문서에 기록한다.

### Phase 1에서 아직 하지 않는 것

- LLM 호출, AI Review, RAG ingestion/vector search, Tool Calling, LangGraph
- 실제 파일 업로드, 이메일·메신저 알림, 복잡한 결재선, 정책 관리 UI
- Cloud 배포 최적화와 대규모 부하 대응

이 기준을 모두 만족하면 AI가 없어도 업무 상태와 권한이 정확한 기반이 마련된 것으로 보고 Phase 1을 완료한다.
