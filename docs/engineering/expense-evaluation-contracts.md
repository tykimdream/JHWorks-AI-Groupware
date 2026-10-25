# 경비 평가 계약과 검증 범위 — M0-01 / M2-01

## 무엇을 재사용하고 확장했는가

기존 자연어 초안·후속 질문·정책 RAG·확인 저장 엔진을 재사용한다. 기존 추출 평가6개를 보존하고
추가30개로 총36개를 정의했다. 금액6 / 날짜5 / 후속 답변7 / 분류7 / 누락 사실8 / 신뢰 경계3개다.
필수 사례10개를 평가 manifest와 대조한다. 데이터/프롬프트 버전을 report의 hash/version으로 연결한다.

| 계층 | 이번에 확인할 것 | 의미하지 않는 것 |
| --- | --- | --- |
| dataset-contract | 필드명·타입·날짜·중복 ID·충돌 기대값·범주·필수 gate의 유효성 | 모델이 36개 요청을 정확히 해석했다는 결과 |
| 채점 회귀 | 잘못된 intent/금액/조작 사실과 null·0의 차이를 탐지 | 골드 값을 출력으로 사용한 모델 정확도 |
| 기존 서비스/API 회귀 | 질문·정책·서명 토큰·멱등 저장·권한·문서 상태 | fake provider를 실제 모델로 바꾼 품질 |
| model 평가 | 실제 provider 응답과 같은 채점 함수를 비교 | 아직 실행하지 않았으므로 새 정확도/지연/비용 없음 |

## 안전한 offline 명령

```sh
pnpm eval:expense:offline
# 또는 apps/api에서
uv run python -m app.evals.draft_contract
```

이 경로는 설정·DB·provider factory·모델 SDK를 불러오지 않는다. 해당 모듈 import를 차단한 별도 프로세스로 검증한다.
기존 candidate가 models 패키지 경유로 DB engine/settings를 초기화하던 의존을 끊기 위해 ExpenseCategory를
공통 값 모듈로 옮겼다. models.enums의 기존 import는 같은 enum을 재수출하며 API 값/DB 스키마는 바뀌지 않는다.

결과는 `evaluationKind=dataset-contract`, `modelEvaluationStatus=not-run`, `providerCalls=0`이다.
모델 pass rate·latency·tokens는 null이다. 이 report를 실제 모델 suite gate에 넣으면 invalid_report로 거절한다.
이전 모델 평가 report의 미표기 kind는 호환성을 위해 유지하며 새 추출 평가는 kind=model을 명시한다.

다음 검사들은 실제 모델 호출 없이 실행한다.

```sh
cd apps/api
uv run pytest tests/test_draft_eval_contract.py tests/test_eval_suite.py \
  tests/test_eval_encoding.py tests/test_expense_model_smoke.py \
  tests/test_approval_draft_ai.py tests/test_expense_approval.py
```

## 실제 모델 평가와의 경계

기존 `pnpm eval:approval-draft` / `eval:all`은 외부 모델 평가 경로다. 새36개 사례 전체를 실행하면
기존6개보다 호출이 늘 수 있으므로 비용·호출 범위를 준비한 뒤 실행한다. 일반 CI에서는 호출하지 않는다.
기존 제한 smoke는 같은 두 case ID만 선택하고 최대2회·재시도0·첫 실패 시 중단 계약을 유지한다.
이번에는 실행하지 않았으며 [기존 실제2건](expense-model-smoke.md)을 재검증한 것으로 표시하지 않는다.

정확 일치 채점은 지정한 구조화 사실과 null 여부를 다룬다. 자유로운 제목·본문의 문장 품질,
전반적인 추론 정확도·RAG 관련성·사람의 효율을 측정하지 않는다.
현재 모든 추출 사례의 목표 문턱은 기존처럼1.0이며 필수10개는 낮은 총 통과율 기준을 택하더라도 별도로 남는다.

## 기존 회귀와의 연결

- test_approval_draft_ai: 추가 질문의 무저장, 후속 답변/서울 날짜 전달, hash/actor 확인, 멱등 저장, provider failure.
- test_expense_approval: 경비 저장·수정·제출·승인, 미완성 초안/제출 차이, 정책 유형과 증빙 참조 한계.
- test_expense_checks: 읽기 전용 중복 근거, 열람 권한·workspace 경계·점검 범위.
- 방문자/서명 토큰/정책 검색의 기존 회귀는 유지한다. 동일 동작 테스트를 36개 새 모델 사례와 중복 집계하지 않는다.

다음 구현은 M2-02의 서버 capability/예산 계약이다. 그 전에 M1-01에서 기존 정리 증거와 현재 운영의 차이만 대조한다.
