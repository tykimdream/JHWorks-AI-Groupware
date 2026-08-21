# Phase 2 — AI Approval Review

상태: **구현 완료, live model smoke test 대기 (2026-08-21)**

## 1. 목표

작성자가 결재 Draft를 제출하기 전에 문서의 의미상 누락, 명확성, 표현 품질과 일반적인 위험을 AI로 검토한다. 결과는 구조화된 계약으로 반환하고, AI는 원문을 수정하거나 제출하지 않는다.

이번 단계는 RAG와 Agent를 도입하지 않는다. 회사 정책에 근거한 판단과 인용은 Phase 3에서 추가한다.

## 2. 사용자 시나리오

1. 작성자가 자신의 Draft 상세 화면을 연다.
2. `AI로 검토하기`를 실행한다.
3. 서버가 문서 version과 작성자 권한을 확인한다.
4. 일반 코드가 필수 field, 날짜 순서와 금액 합계를 먼저 검사한다.
5. LLM이 목적의 명확성, 의미상 누락, 표현 품질과 민감정보 위험을 검토한다.
6. 서버가 두 결과를 하나의 응답으로 합치고 점수를 계산한다.
7. 사용자는 issue별 근거와 수정 제안, 선택적인 수정 문안을 확인한다.
8. 검토 중 원문 version이 바뀌었다면 결과를 stale로 표시하고 자동 적용하지 않는다.

## 3. 책임 분리

| 영역 | 일반 코드 | LLM |
| --- | --- | --- |
| 입력과 권한 | 인증, 작성자 확인, DRAFT 상태, version 일치 | 담당하지 않음 |
| 구조 검증 | 필수 field, 날짜 순서, 비용 합계 | 담당하지 않음 |
| 의미 검토 | 결과 schema와 enum 재검증 | 목적 명확성, 문맥상 누락, 표현 품질, 일반 위험 |
| 정책 판단 | Phase 2에서는 제공하지 않음 | 정책 위반을 단정하거나 정책을 인용하지 않음 |
| 데이터 변경 | 기존 Draft 수정 API와 제출 command만 가능 | 원문 수정과 제출 권한 없음 |
| 점수 | severity별 고정 감점으로 계산 | 점수를 직접 결정하지 않음 |

## 4. API 계약

### 요청

```http
POST /api/v1/approvals/{approvalId}/ai-review
```

```json
{
  "version": 3
}
```

### 응답

```json
{
  "approvalId": "apr_123",
  "approvalVersion": 3,
  "currentApprovalVersion": 3,
  "isStale": false,
  "status": "NEEDS_REVISION",
  "score": 72,
  "issues": [
    {
      "code": "LLM_CLARITY_1",
      "source": "LLM",
      "severity": "MEDIUM",
      "category": "CLARITY",
      "field": "content",
      "message": "방문 후 기대하는 결과가 명확하지 않습니다.",
      "suggestion": "합의할 범위와 산출물을 한 문장으로 추가하세요."
    }
  ],
  "revisedContent": "...",
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "promptVersion": "approval-review-v1",
  "usage": {
    "inputTokens": 640,
    "outputTokens": 210,
    "totalTokens": 850
  },
  "latencyMs": 820,
  "reviewedAt": "2026-08-21T10:00:00Z"
}
```

## 5. Structured Output

LLM output은 다음 항목으로 제한한다.

- `issues`: `COMPLETENESS`, `CLARITY`, `WRITING`, `RISK` category의 구조화된 issue
- `severity`: `INFO`, `LOW`, `MEDIUM`, `HIGH`
- `field`: 공개된 결재 field 또는 `document`
- `message`: 관찰한 문제
- `suggestion`: 사용자가 선택적으로 반영할 수정 방향
- `revisedContent`: 원문을 대체하지 않는 선택적 제안 문안

응답 형식이 맞아도 사실성과 업무 적합성이 보장되는 것은 아니다. 서버는 enum, 길이, issue 개수를 다시 제한하고 정책 근거가 없는 정책 주장을 허용하지 않는다.

## 6. 점수와 상태

점수는 LLM이 아니라 서버가 계산한다.

- 시작 점수: 100
- `HIGH`: 25점 감점
- `MEDIUM`: 15점 감점
- `LOW`: 8점 감점
- `INFO`: 감점 없음
- 최소 점수: 0
- issue가 하나라도 있으면 `NEEDS_REVISION`, 없으면 `PASS`

이 점수는 승인 가능성을 의미하지 않으며 검토 결과를 빠르게 비교하기 위한 보조 지표다.

## 7. 실패 처리

- API key 미설정: `503 AI_REVIEW_UNAVAILABLE`
- provider timeout 또는 일시 장애: `503 AI_REVIEW_UNAVAILABLE`
- LLM refusal 또는 parsing 실패: 원문을 변경하지 않고 명시적으로 실패
- 권한 없음: `403`
- DRAFT가 아님: `409 INVALID_STATUS`
- 요청 version 불일치: `409 VERSION_CONFLICT`
- 호출 중 version 변경: 정상 응답하되 `isStale=true`

실패 시 자동으로 제출하거나 검토를 통과한 것으로 간주하지 않는다.

## 8. 개인정보와 관측성

- provider에는 검토에 필요한 결재 field만 전송한다.
- 직원 email, 조직 전체, 결재선과 session 정보는 보내지 않는다.
- 원문과 prompt 전체를 application log에 남기지 않는다.
- provider, model, prompt version, latency, token usage, 결과 상태와 오류 code를 기록한다.
- OpenAI Responses API 요청은 저장하지 않도록 `store=false`를 사용한다.

## 9. 평가

최소 평가 case는 다음을 포함한다.

- 명확하고 완전한 정상 문서
- 목적이 모호한 문서
- 필수 정보가 누락된 문서
- 금액과 비용 세부 합계가 다른 문서
- 지나치게 구어체인 문서
- 개인정보 또는 민감정보가 포함된 문서
- Prompt Injection 형태의 문구가 포함된 문서

CI에서는 외부 API를 호출하지 않고 결정적 검사, provider contract와 결과 병합을 fake provider로 검증한다. 실제 모델 평가는 명시적인 별도 명령으로 실행하고 model과 prompt version별 결과를 비교한다.

## 10. 완료 조건

- 작성자만 자신의 DRAFT를 AI 검토할 수 있다.
- OpenAI Responses API와 Pydantic Structured Output을 사용한다.
- 결정적 issue와 LLM issue가 출처를 유지한 채 합쳐진다.
- 원문을 자동 수정하거나 제출하지 않는다.
- 검토 결과에 문서 version, model, prompt version, latency와 token usage가 포함된다.
- stale 결과를 backend와 frontend에서 식별한다.
- 정상, 누락, 권한 위반, provider 실패, version 충돌을 자동 테스트한다.
- 실제 API key 없이 전체 기본 test suite를 실행할 수 있다.
- UI에서 loading, success, stale, error 상태를 확인할 수 있다.

## 11. 제외 범위

- 정책 검색, embedding, vector database와 정책 section 인용
- AI 제안의 자동 반영
- 검토 결과 DB 영구 저장과 이력 UI
- multi-turn 대화, Tool Calling, LangGraph
- 자동 제출, 승인 또는 반려

## 12. 다음 단계

Phase 3에서 정책 section retrieval을 추가하고 issue에 `policyId + version + sectionId` 근거를 연결한다. Phase 2의 provider, schema, version과 평가 경계를 그대로 유지하면서 policy-grounded review로 확장한다.
