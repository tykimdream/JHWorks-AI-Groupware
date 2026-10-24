# 경비 실제 모델의 제한된 점검 — 2026-10-24

사용자가 직접 저장한 기존 키를 로컬에서 사용했다. 키 파일은 Git 제외·0600이며 앱의 AI_ENABLED=false는 유지한다.
새 API 키/클라우드 Secret/IAM을 만들거나 업로드하지 않았다.

`app.ops.expense_model_smoke`는 기본적으로 계획만 출력한다. `--execute`일 때만 고정 합성 요청 2건을 순서대로 호출하며,
자동 재시도0·요청당 timeout20초·출력 최대1,600토큰이다. 실패/품질 불일치 시 즉시 중단하고 진단 원문/키를 출력하지 않는다.
일반 제공자의 기본 재시도1 계약은 보존하고 이 CLI만 0을 전달한다.
업무 DB/문서/클라우드 설정을 변경하지 않으며 전체 평가 dataset을 무제한 반복하지 않는다.

## 실제 결과

모델 `gpt-5.4-mini-2026-03-17`, 시도2건/성공2건.

| 합성 사례 | 확인 | 입력/출력 토큰 | 응답 시간 |
| --- | --- | --- | --- |
| past-spend-is-expense | EXPENSE 분류·17만원과 미제공 지출 사실의 null 유지 | 950 / 122 | 3,947ms |
| multi-turn-ces-expense | 후속 답변의 날짜·사용처·교통비·목적·증빙 참조 추출 | 989 / 182 | 2,050ms |

이는 고정 합성 사례 2건의 점검이며 통계적 정확도, 전체 모델 평가, 실제 사용자 자료 검증이나 공개 AI 연결 성공을 뜻하지 않는다.
키 유효성을 실제로 확인했지만 공개 데모는 여전히 AI off이다. 증빙은 참조 문자열이며 원본 파일 검증이 아니다.

## 비공개 제품 배포

제품 source main `508bada887ed1dca3d29c8ff5b59fa2e208e5246`의 CI 성공 후
[release 40087293764](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/40087293764)가 성공했다.
`jhworks-staging-508bada887ed`에 API/web 고정 digest를 배포하고 liveness/readiness/보호 API401/web200 4개를 확인했다.
기존 복원 검증 백업 `20261022T105221Z-0db223a2`를 참조했으며 이번에 새 백업을 만든 것으로 표시하지 않는다.
이 제품 변경에는 Alembic revision 추가가 없다. demo 별도 서비스와 공개 도메인의 배포 완료는 별도 검증이 필요하다.

## 재현

```sh
cd apps/api
uv run python -m app.ops.expense_model_smoke
# 합성 데이터 2건의 유료 호출을 의도한 경우에만:
uv run python -m app.ops.expense_model_smoke --execute
```

합성 제공자 회귀는 계획 시 키/client 미사용, 키 부재, 최대2건/재시도0, 최초 실패 시 중단·진단 미노출을 검증한다.
[OpenAI 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-mini)의 모델과 Structured Output 지원을 확인했다.
