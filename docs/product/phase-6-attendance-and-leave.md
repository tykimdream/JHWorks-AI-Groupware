# Phase 6 — Attendance and Leave Workflow

상태: **완료 — Checkpoint 12 완료 (2026-08-25)**

## 1. 목표

휴가 가능일 추천을 AI의 일반 지식이나 prompt 안의 임시 데이터로 만들지 않는다. 근태와 휴가를 그룹웨어의 정식 application domain으로 구축하고, 전자결재와 AI가 함께 사용할 수 있는 휴가 잔여 내역과 일정 조회 계약을 먼저 만든다.

## 2. Checkpoint 10 범위

- 직원별·연도별 휴가 계정
- 전사 행사, 공휴일, 부서 프로젝트 마일스톤, 직원 휴가 일정
- 현재 사용자에게 필요한 일정만 반환하는 근태 overview API
- 실제 업무와 무관한 JHWorks synthetic seed data
- migration, schema, service authorization과 API integration test

Checkpoint 11에서 이 기반을 휴가 결재 상태 전이에 연결했다.

## 3. Domain Model

### LeaveAccount

| 필드 | 의미 |
| --- | --- |
| `employeeId`, `year` | 직원과 귀속 연도의 unique account |
| `grantedDays` | 해당 연도 부여 일수 |
| `carriedOverDays` | 전년도 이월 일수 |
| `usedDays` | 승인 완료되어 사용된 일수 |
| `pendingDays` | 승인 대기 중이라 예약된 일수 |
| `availableDays` | `부여 + 이월 - 사용 - 대기`로 계산한 가용 일수 |
| `version` | 이후 휴가 결재 확정 시 동시성 제어에 사용할 version |

모든 일수는 0.5일 단위를 표현할 수 있는 decimal이다. 구성 값은 음수가 될 수 없고, `사용 + 대기`가 `부여 + 이월`을 초과하지 않도록 DB constraint로 막는다.

기존 Employee의 단일 `leaveBalance`는 기존 API 호환을 위해 당분간 유지한다. 새 근태 API와 업무 조회 Tool은 연도별 LeaveAccount를 우선 source of truth로 사용한다.

### WorkCalendarEvent

| 구분 | 값 |
| --- | --- |
| category | `COMPANY_EVENT`, `PROJECT_MILESTONE`, `HOLIDAY`, `LEAVE` |
| scope | `COMPANY`, `DEPARTMENT`, `EMPLOYEE` |
| status | `TENTATIVE`, `CONFIRMED`, `CANCELED` |
| impact | `NONE`, `CAUTION`, `BLOCKED` |

`impact`는 추천 점수 자체가 아니라 결정적 availability engine이 사용할 입력이다. 예를 들어 공휴일과 필수 프로젝트 기간은 `BLOCKED`, 팀원의 휴가는 중복 인원에 따라 판단할 `CAUTION`으로 제공한다.

## 4. API 계약

```http
GET /api/v1/attendance/overview?startDate=2026-09-01&endDate=2026-09-30
```

조회 기간은 최대 93일이다. 응답은 다음 세 그룹을 분리한다.

- `leaveBalances`: 조회 연도에 해당하는 현재 사용자의 휴가 계정
- `calendarEvents`: 전사 일정과 현재 사용자의 부서 일정
- `teamLeaves`: 현재 사용자와 같은 부서 직원의 휴가 기간, 상태와 영향도

## 5. Authorization과 개인정보

- 인증된 사용자만 조회할 수 있다.
- 전사 일정은 모든 직원에게 보인다.
- 부서 일정은 현재 사용자의 부서 일정만 보인다.
- 직원 휴가는 같은 부서의 일정만 보인다.
- 팀 휴가 응답은 직원 ID, 이름, 직책과 기간만 제공한다.
- 휴가 사유, email, 결재 본문과 다른 부서의 개인 일정은 노출하지 않는다.
- 취소된 일정은 recommendation input에서 제외한다.

이 경계는 UI나 LLM prompt가 아니라 backend query에서 적용한다.

## 6. Synthetic Data

2026년 기준으로 다음의 완전히 가상인 일정이 포함된다.

- JHWorks 전사 타운홀
- JHWorks 창립기념 휴무
- Sales 3분기 파이프라인 리뷰
- Engineering Groupware 0.2 릴리스
- Sales 팀원 2명의 확정·예정 휴가

같은 기간을 Sales와 Corporate Operations 사용자가 조회하는 테스트로 부서 간 정보 격리를 검증한다.

## 7. 완료 조건

- migration이 새 환경과 기존 local DB에서 적용된다.
- seed가 재실행되어도 휴가 계정과 일정이 중복되지 않는다.
- 휴가 가용 일수가 저장값이 아니라 구성 요소에서 계산된다.
- 전사·부서·직원 scope가 잘못된 target과 결합되지 않도록 DB가 제한한다.
- 다른 부서의 프로젝트와 직원 휴가를 API가 반환하지 않는다.
- 역전된 날짜와 93일 초과 조회를 거절한다.
- API key 없이 전체 기본 검증을 실행할 수 있다.

## 8. Checkpoint 11 — 휴가 전자결재

`LEAVE`를 일반 결재의 제목만 바꾼 문서가 아니라 별도의 structured details로 제공한다.

| 필드 | 의미 |
| --- | --- |
| `leaveType` | 현재 지원하는 연차 유형 `ANNUAL` |
| `leaveUnit` | 종일, 오전 반차, 오후 반차 |
| `startDate`, `endDate` | 휴가 시작·종료일 |
| `requestedDays` | 서버가 계산하고 저장한 실제 차감 일수 |
| `reason` | 선택 입력이며 팀 캘린더에는 노출하지 않음 |
| `handoverNote` | 결재자에게 전달할 선택 인수인계 메모 |

Draft 저장 시 클라이언트가 보낸 `requestedDays`는 사용하지 않는다. 서버가 주말과 현재 사용자의 범위에 적용되는 `CONFIRMED` 휴무일을 제외해 다시 계산한다. 반차는 하나의 유효한 근무일에만 신청할 수 있고, 하나의 신청은 연도를 넘을 수 없다.

### 상태 전이와 회계 처리

```text
DRAFT
  └─ submit  → pendingDays 증가 + TENTATIVE 캘린더 이벤트
       ├─ approve → pendingDays 감소 + usedDays 증가 + CONFIRMED 이벤트
       └─ reject  → pendingDays 감소 + CANCELED 이벤트
                        └─ revise/edit/resubmit → 새 일수 예약 + 기존 이벤트 재사용
```

Approval, ApprovalLine, LeaveAccount, WorkCalendarEvent 변경은 하나의 DB transaction에서 commit한다. LeaveAccount와 연결 이벤트는 상태 전이 시 잠가 중복 승인과 동시에 제출되는 요청의 초과 예약을 방지한다. 가용 일수가 부족하면 `INSUFFICIENT_LEAVE_BALANCE`, 연도 계정이 없으면 `LEAVE_ACCOUNT_UNAVAILABLE`, 예약 상태가 맞지 않으면 `LEAVE_RESERVATION_INCONSISTENT`로 실패하며 결재 상태도 변경하지 않는다.

WorkCalendarEvent의 nullable unique `approvalId`가 휴가 결재와 일정의 1:1 연결을 보장한다. 팀 캘린더 API는 기존과 동일하게 사유·인수인계·결재 본문을 반환하지 않는다.

### 사용자 화면

- 직접 작성 화면에서 휴가 신청, 종일·반차, 기간, 사유와 인수인계를 입력한다.
- 화면의 예상 일수는 주말을 제외한 빠른 안내이며, 저장 결과의 확정 일수는 회사 휴무일까지 반영한 서버 값이다.
- 목록에서는 금액 대신 차감 일수를 표시한다.
- 상세 화면에서 휴가 단위, 확정 차감 일수, 기간과 결재자용 정보를 확인한다.

### 검증 범위

- 클라이언트가 임의로 보낸 일수를 서버 계산값으로 교체
- 기간에 포함된 주말과 JHWorks 확정 휴무일 제외
- 오전·오후 반차 0.5일 계산
- 제출·승인 시 `pendingDays`와 `usedDays` 전환
- 반려 시 예약 복원, 수정 후 재제출 시 기존 일정 재사용
- 잔여 일수 부족 시 결재·계정·일정 무변경

## 9. Checkpoint 12 — 결정적 휴가 가능일 탐색

휴가 가능 여부는 LLM prompt가 아니라 application service가 계산한다. 같은 사용자·휴가 계정·일정·입력에는 항상 같은 후보와 판단 근거를 반환한다.

### API 계약

```http
GET /api/v1/attendance/leave-availability
    ?startDate=2026-09-01
    &endDate=2026-09-30
    &requestedDays=2.0
    &limit=6
```

- 탐색 범위는 최대 93일이며 하나의 연도 안에 있어야 한다.
- 지원 일수는 반차 `0.5` 또는 정수 `1~5`일이다.
- 응답은 연차 계정, 정렬된 후보, 날짜별 판단 신호와 전체 실패 사유를 분리한다.
- 데이터가 부족해도 모호한 빈 배열 대신 `ACCOUNT_UNAVAILABLE`, `INSUFFICIENT_BALANCE`, `NO_CANDIDATE` 상태를 반환한다.

### 날짜 판단 규칙

| 입력 | 결정 |
| --- | --- |
| 주말 | 연차 차감일에서 제외하고 날짜 신호는 `BLOCKED` |
| 확정 휴무일 | 연차 차감일에서 제외하고 `BLOCKED` |
| 확정 `BLOCKED` 회사·프로젝트 일정 | 후보에서 제외 |
| 예정 `BLOCKED` 일정 | 확정 전이므로 `CAUTION`으로 완화 |
| `CAUTION` 회사·프로젝트 일정 | 후보는 유지하되 주의 근거 표시 |
| 같은 팀의 예정·확정 휴가 | 후보는 유지하되 익명화된 건수로 `CAUTION` |
| 본인의 예정·확정 휴가 | 중복 신청 방지를 위해 `BLOCKED` |
| 잔여 연차 부족 | 후보를 만들지 않고 안정적인 실패 상태 반환 |

종일 후보는 연속된 **차감 근무일**을 기준으로 만든다. 중간의 주말과 휴무일은 건너뛰므로, 예를 들어 9월 23일과 28일을 2일 후보로 제안할 수 있다. 확정 휴무일인 24~25일과 주말은 실제 차감일에 포함되지 않는다.

후보 정렬은 다음 순서의 일반 코드다.

1. 충돌이 없는 `AVAILABLE` 후보
2. `CAUTION` 후보
3. 주의 근거 수가 적은 후보
4. 시작일이 빠른 후보

### 개인정보와 AI 경계

- 후보 계산은 현재 actor의 연도별 휴가 계정만 조회한다.
- 공유 일정은 전사와 현재 부서 범위만 사용한다.
- 팀 휴가는 같은 부서만 계산하며 이름, email, 사유와 결재 본문을 응답하지 않는다.
- API 응답의 `eventIds`는 계산 근거 추적용이며 다른 직원 정보는 포함하지 않는다.
- AI는 이후 자연어 날짜를 구조화하거나 계산 결과를 설명할 수 있지만 후보 상태·차감 일수·충돌 여부를 변경할 수 없다.

### 사용자 화면

- 주 메뉴에 `근태·휴가` 화면을 추가했다.
- 탐색 기간과 0.5~5일을 선택해 최대 6개 후보를 조회한다.
- 잔여 연차, 계산 상태, 추천 수와 날짜별 가능·주의·제외 신호를 함께 표시한다.
- 후보에서 `이 날짜로 휴가 Draft 작성`을 누르면 휴가 유형, 단위와 날짜가 전자결재 작성 화면에 자동 입력된다.
- Draft 저장과 제출은 기존 전자결재 권한·검증·명시적 사용자 행동을 그대로 사용한다.

### 검증 범위

- 같은 입력의 응답 결정성
- 충돌 없는 후보 우선 정렬
- 회사 행사와 팀 휴가의 주의 후보
- 프로젝트 핵심 일정과 본인 휴가의 차단
- 주말·확정 휴무일을 건너뛴 차감 근무일 구성
- 반차 후보, 잔여 부족과 계정 없음
- 다른 직원 이름·email 비노출
- 잘못된 기간·연도·지원하지 않는 1.5일 입력 거절

## 10. 다음 체크포인트

Checkpoint 13에서는 자연어 휴가 요청을 실제 날짜·탐색 범위·희망 일수로 구조화하고, 이번 결정적 API 결과를 AI가 근거와 함께 설명하도록 연결한다. Draft 저장과 제출 같은 쓰기 Tool은 exact preview, 명시적 확인, idempotency와 stale account 검증을 각각 적용한다.
