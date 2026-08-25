# Phase 6 — Attendance and Leave Foundation

상태: **진행 중 — Checkpoint 10 완료 (2026-08-25)**

## 1. 목표

휴가 가능일 추천을 AI의 일반 지식이나 prompt 안의 임시 데이터로 만들지 않는다. 근태와 휴가를 그룹웨어의 정식 application domain으로 구축하고, 전자결재와 AI가 함께 사용할 수 있는 휴가 잔여 내역과 일정 조회 계약을 먼저 만든다.

## 2. 이번 체크포인트의 범위

- 직원별·연도별 휴가 계정
- 전사 행사, 공휴일, 부서 프로젝트 마일스톤, 직원 휴가 일정
- 현재 사용자에게 필요한 일정만 반환하는 근태 overview API
- 실제 업무와 무관한 JHWorks synthetic seed data
- migration, schema, service authorization과 API integration test

휴가 결재 생성·승인과 추천 후보 계산은 다음 체크포인트에서 연결한다.

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

## 8. 다음 체크포인트

Checkpoint 11에서는 `LEAVE` 결재 details를 실제 생성·제출·승인 workflow에 연결한다. 승인 대기 시 `pendingDays`, 승인 시 `usedDays`와 근태 캘린더를 transaction으로 갱신한다.

Checkpoint 12에서는 공휴일·주말·회사 행사·프로젝트 기간·팀 휴가·잔여 일수를 일반 코드로 계산해 여러 휴가 후보와 제외 사유를 만든다. AI는 계산된 후보를 설명하고 자연어 요청을 구조화하지만 날짜 가능 여부를 직접 결정하지 않는다.
