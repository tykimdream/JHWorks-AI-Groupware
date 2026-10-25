# 공개 경비 AI와 비용 원장 연결 — M2-02B2

코드는 opt-in 연결을 제공하지만 **기본 OFF이며 원격 적용·실제 모델 실행은 하지 않았다**.
공개 여부와 모델 평가 결과는 이 문서의 구현 설명과 구분한다.

## 허용 범위와 설정

`JHWORKS_PUBLIC_DEMO_ENABLED=true`, 기존 전역 `JHWORKS_AI_ENABLED=false`를 유지한다.
별도 `JHWORKS_PUBLIC_EXPENSE_AI_ENABLED=true`와 유효한 `JHWORKS_PUBLIC_EXPENSE_AI_BUDGET`,
키, `approval_draft` allowlist가 모두 있어야 경비 초안의 scoped dependency가 연결된다.
일반 provider factory/eval 경로에서는 공개 키가 있어도 draft client를 생성하지 않는다.
다른 유료 기능(문서 검토·휴가/업무 agent·embedding)은 공개 모드에서 계속 차단한다.

| 설정 제약 | 구현 상한 |
| --- | --- |
| 일 비용 | 307,200~500,000 micro USD |
| 월 비용 | 일 예산 이상, 최대 2,000,000 micro USD |
| 전체 일 admission | 최대10회 |
| 공간별 일 admission | 최대5회, 작성자·결재자 공유 |
| 동시 provider 요청 | 전체1개 |
| 원문/후속 답변 | 요청2,000자, 답변 각각2,000자·최대8개 |
| 출력/재시도 | 최대1,600토큰 / SDK retry0 |
| 네트워크 | SDK timeout20초, 플랫폼 요청 제한과 별도 |

이것은 켤 수 있는 **코드 상한**이며 실제 운영 예산을 승인·설정한 기록이 아니다.
`public_demo_service_manifest`도 새 기능을 명시적으로 OFF로 렌더링한다.
기존 전역 AI 스위치를 켜서 공개 기능을 활성화하는 구성은 계속 거부한다.

## 가격 기준과 보수적인 예약

2026-10-25 확인한 [공식 모델 정보](https://developers.openai.com/api/docs/models/gpt-5.4-mini)의
`gpt-5.4-mini-2026-03-17`을 고정한다. 일반 텍스트 입력/출력은100만토큰당 $0.75/$4.50이다.
공식 endpoint와 `service_tier=default`를 지정한다. SDK 환경의 다른 base URL을 공개 경로에 상속하지 않는다.
[Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)의
최대 출력은 reasoning을 포함하며, 유료 tool/이전 response/추가 embedding 단계는 요청하지 않는다.

입력 바이트를 토큰으로 추정하는 대신 모델의 전체 입력 context 상한400,000토큰과 출력1,600토큰을
예약한다. 요청당 **307,200 micro USD ($0.3072)**는 예상 비용이 아니라 보수적인 예약이다.
검증된 사용량으로 표준 요금을 계산해 올림 정산하고, cache 할인은 반영하지 않아 실제 청구보다 클 수 있다.
월 잔액이 한 요청의 예약보다 적으면 짧은 요청도 차단한다. 이 사용 가능성의 손해를 비용 경계와 교환했다.

세금·환율·다른 서비스의 과금·제공자 가격 변경은 이 계산에 포함되지 않는다. GCP spend cap과 별개이며
프로젝트 전체 원화 청구액의 절대 상한을 보장하지 않는다. 실제 활성화 전에 공식 가격·모델 접근과
월 전체 AI 예산(평가 포함)을 다시 확인해야 한다. pinned model도 영구적인 가격 고정을 뜻하지 않는다.

## 서버의 순서

1. 인증 dependency가 DB의 방문 공간·직원·소속·만료를 검사하고 기존 요청 admission을 커밋한다.
2. 별도 세션에서 원장의 전역 잠금을 잡아 최대 비용을 예약·커밋한다.
3. 대기 중 만료/비활성화/소속 변경을 놓치지 않도록 새 세션에서 신원을 재검사한다.
   여기서 거부되면 아직 provider를 구성하지 않았으므로 비용0으로 정산한다. admission 횟수는 유지한다.
4. 그 뒤에만 고정 모델 client를 생성·호출한다. 정상 응답은 model/tier와 사용량 합계를 확인해 정산한다.
5. 서버의 기존 경비 누락/미래 날짜/양식 검증을 거친다. 경비가 아닌 intent는 UNSUPPORTED이며 토큰이 없다.
6. 사용자 확인 토큰을 받은 저장만 문서를 생성한다. 반복 확인은 idempotent이고 제출·승인은 별도다.

공개 초안의 정책 검색은 UNAVAILABLE와 빈 근거로 명시한다. 주입된 embedding provider라도 호출하지 않는다.
규정이 확인됐다고 주장하지 않으며 경비 사전 점검·직접 정책 확인·수동 결재를 이용한다.

## 실패와 화면

- 다른 요청 처리 중은 `AI_BUSY`, 기간/공간 비용·횟수 한도는 `AI_BUDGET_EXHAUSTED`로 구분한다.
- SDK/파싱 오류는 청구0으로 단정하지 않고 예약 전액을 UNCERTAIN으로 처리한다. 숨은 retry는 없다.
- 모델/tier 불일치·사용량 부재/모순/상한 초과는 전액 처리 후 전역 동결한다. 동결은 날짜가 바뀌어도 유지된다.
- 정산 DB 장애는 후보를 사용자에게 성공 응답하지 않는다. 남은 예약/슬롯은 보존한다.
- UI는 소진·일시 처리 중·중단을 구분하고, 같은 화면의 요청/답변과 수동 작성 링크를 보존한다.
  **수동 작성 화면으로 이동한 뒤 본문 자동 이관은 아직 없으며**, 필요하면 사용자가 원문을 복사해야 한다.
- 공개 홈/초안은 경비만 안내한다. 설정 API는 공간별 요청 상한을 제공한다. 전체 예산 잔액을 보장하는 값은 아니다.

## 중단된 예약 복구

자동 lease 만료나 자동 환불을 제공하지 않는다. 읽기 기본값의 도구는 오래된 예약을 최대5개만 조회한다.

```sh
cd apps/api
uv run python -m app.ops.ai_budget_reconcile
```

적용 전 운영자가 공개 AI를 OFF로 배포하고 이전 실행이 더 이상 provider를 호출하지 않음을 확인해야 한다.
로컬 설정 OFF만으로 원격 프로세스가 중지됐다고 판단하지 않는다. 원장·provider 기록을 대조하고
명시적 예약 ID 최대5개, 10분 이상 경과한 RESERVED/UNCERTAIN만 선택한다.

```sh
# 실제 운영 중단과 대상 대조가 끝난 뒤 별도 승인 범위에서만 실행
uv run python -m app.ops.ai_budget_reconcile \
  --reservation-id air_REVIEWED_ID --apply --confirm-no-live-provider-calls
```

원래 기간에 예약 전액을 비용으로 처리해 슬롯을 해제한다. 비용·횟수는 환불하지 않으며 전역 동결도 풀지 않는다.
동일 UNCERTAIN 재실행은 중복 비용이 없다. 건별 커밋이므로 경합/오류 시 앞선 건은 이미 반영됐을 수 있다.
다시 조회해 결과를 대조해야 한다. 실제 사용량과 다른 terminal 정산은 덮어쓰지 않는다.
동결 해제는 원인·가격·모델·배포를 검증한 후 별도 운영 변경으로 다룬다. 이 도구를 원격 실행하지 않았다.

## 검증과 남은 외부 단계

합성 provider와 격리 DB에서 예약 전 client 미생성, role 공유, 재검사, 불명/비정상 응답 동결,
후속 입력 상한, paid embedding 미호출, 명시적 저장/재전송/제출/역할 승인과 복구를 검사한다.
브라우저의 공개 AI/소진 상태는 명시적 mock이며 실제 모델 품질 결과가 아니다.

[M2-03A의 예산 제한 평가 준비](bounded-expense-model-evaluation.md)는 기본 계획만 제공한다.
M2-03에서 실제 키·모델 접근·총 평가 예산/호출 상한, 고정 사례 평가, 실제 원격 migration과
source/digest 후보, OFF·실패·소진 흐름을 확인해야 한다. 키 업로드·유료 호출·공개 활성화는 아직 수행하지 않았다.
보관 한도/정리·백업 조건은 M1-02 기록과 별도 대조한다. 일반 CI는 합성 provider만 사용한다.
