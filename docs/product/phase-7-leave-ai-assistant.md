# Phase 7 — Grounded Leave AI Assistant

상태: **Checkpoint 14 완료 (2026-08-25)**

## 1. 목표

자연어 휴가 질문을 `Asia/Seoul` 기준 실제 날짜, 탐색 범위와 희망 일수로 구조화하고,
Checkpoint 12의 결정적 availability service와 활성 휴가 정책 RAG 결과를 사용해 설명한다.
상담 단계는 조회 전용이며 Approval row를 만들지 않는다.

## 2. 책임 분리

| 계층 | 책임 |
| --- | --- |
| LLM Structured Output | `CHECK_DATES`/`RECOMMEND_DATES` 의도, 실제 시작·종료일, 희망 일수 추출 |
| 일반 코드 | 날짜 순서, 동일 연도, 최대 93일, 0.5 또는 정수 1~5일 검증 |
| Availability service | 휴가 계정, 차감, 휴일, 회사·프로젝트 일정, 본인·팀 휴가와 후보 상태 계산 |
| Policy RAG | 현재 활성 `LEAVE` 정책 section만 검색하고 citation key와 원문을 반환 |
| UI | 여러 번의 후속 답변, 확정 날짜, 계산 결과, 정책 검색 상태와 runtime 표시 |

AI 출력 schema에는 availability status, reason code, 후보, 정책 citation이나 쓰기 명령이 없다.
따라서 prompt injection으로 프로젝트 일정을 무시하거나 허위 정책 근거를 요구해도 서버 계산과
활성 정책 allowlist를 변경할 수 없다.

## 3. API 계약

```http
POST /api/v1/leave-assistant/consult
Content-Type: application/json

{
  "request": "9월에 이틀 쉴 날짜 추천해줘",
  "answers": []
}
```

응답은 다음을 분리한다.

- `query`: 모델이 구조화한 의도, 실제 탐색 시작·종료일, 희망 일수
- `questions`: 누락되거나 잘못된 입력을 보충하기 위한 후속 질문
- `availability`: 결정적 service의 원본 status/reason/candidate
- `policyContext`: `READY`, `NOT_INDEXED`, `UNAVAILABLE` 등 검색 상태와 검증 가능한 citation
- `provider`, `model`, `promptVersion`, token usage, latency, 생성 시각

후속 답변은 원래 요청과 `answers` 전체를 다시 전달한다. 서버는 매 round에 완전성을 다시 검사하므로
기간과 희망 일수를 서로 다른 답변에서 보충할 수 있다.

## 4. 실패와 관측성

- 모델 provider 실패는 `503 LEAVE_ASSISTANT_UNAVAILABLE`로 종료하고 어떤 row도 만들지 않는다.
- 정책 색인이 없거나 embedding provider가 실패해도 availability 계산은 유지하고 검색 상태를 명시한다.
- 구조화 결과의 provider/model/prompt version/usage/latency와 결정적 계산 상태를 구조화 로그에 남긴다.
- raw 대화, 다른 직원 이름·email, 비밀정보는 로그에 남기지 않는다.

## 5. 평가와 검증

기본 integration test는 정상 상대 날짜, 여러 번의 모호성 보충, 휴일, 프로젝트 차단, 잔여 부족,
provider 실패, prompt injection과 허위 citation 요구를 포함한다. 실제 모델 평가는 다음 명령으로 분리했다.

```bash
pnpm eval:leave-assistant
```

평가 데이터는 모두 JHWorks synthetic 요청이며 애플리케이션 데이터를 변경하지 않는다.

## 6. Checkpoint 14 — 확인 기반 휴가 Draft Tool

상담의 결정적 candidate를 다음 단계의 exact preview로 변환한다.

- 실제 시작·종료일, 차감 일수와 종일/반차 단위
- 현재 가용 연차와 LeaveAccount version
- 서버가 현재 조직도에서 계산한 최종 결재자
- 활성 휴가 정책 RAG citation과 candidate 주의 사유
- calendar fingerprint와 active policy fingerprint

`POST /leave-draft-tool/prepare`는 읽기만 수행한다. candidate 전체를 기존 availability service로 다시
계산해 일치하는 결과가 없으면 `LEAVE_CANDIDATE_STALE`로 거절한다. 반차 candidate에는 오전/오후 단위,
정수 일수에는 종일 단위만 허용한다.

signed confirmation에는 사용자, confirmation ID, exact preview hash, candidate hash, account version,
calendar fingerprint, manager ID와 policy fingerprint를 결합한다. `POST /leave-draft-tool/confirm`은 다음을
모두 재검증한 뒤 기존 approval service로 `DRAFT`만 만든다.

1. token 만료·서명·현재 actor와 preview/candidate hash
2. 현재 LeaveAccount version, 가용 일수와 차감 일수
3. 현재 manager의 존재·활성 상태·ID
4. 현재 업무 캘린더 fingerprint와 결정적 candidate
5. 활성 휴가 정책 version/content fingerprint

이미 성공한 confirmation ID는 환경이 이후 바뀌어도 같은 Draft를 반환한다. 최초 확인의 동시 재시도는
`approvals.source_confirmation_id` unique constraint와 기존 create service의 충돌 복구로 하나의 row만
생성한다. Draft에는 결재선이 없고 `submittedAt`도 비어 있으며 자동 제출하지 않는다.

테스트는 정상 exact preview, 확인 전 무변경, 만료, token/preview 변조, 다른 사용자, 임의 employeeId,
account/calendar/manager/policy 변경, 중복 confirmation을 포함한다.

## 7. 다음 체크포인트

Checkpoint 15는 Draft 저장 확인과 별도의 제출 preview·확인을 durable state로 관리하고, 두 번째 확인 뒤
기존 submit service를 호출한다. 취소·만료·stale은 무변경으로 종료한다.
