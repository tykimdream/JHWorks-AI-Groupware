# Phase 7 — Grounded Leave AI Assistant

상태: **Checkpoint 13 완료 (2026-08-25)**

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

## 6. 다음 체크포인트

Checkpoint 14는 상담 후보를 exact LEAVE Draft preview로 만들고, 사용자·candidate·account version·calendar
fingerprint에 결합된 signed confirmation을 검증한 뒤에만 하나의 `DRAFT`를 생성한다. 자동 제출은 하지 않는다.
