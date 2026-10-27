# 공개 데모 경비·휴가 AI 연결 준비

이 문서는 로컬 변경의 배포 준비 기록이다. 실제 서비스에 반영되었다는 뜻이 아니다.

- 경비 초안과 휴가 상담은 같은 공개 AI 예산 원장을 사용한다. 각 모델 요청 전에 방문 공간, 일·월 비용, 일별 횟수, 동시 호출을 확인한다. 공개 provider는 고정 모델 `gpt-5.4-mini-2026-03-17`, standard tier, 재시도 0회다.
- 휴가 날짜·연차·일정은 기존 서버가 계산한다. 공개 모드에는 유료 규정 임베딩을 연결하지 않으므로, 상담에서 고른 날짜는 기존 휴가 결재 작성 양식으로 이어진다. 사용자가 확인하고 저장·제출한다.
- 규정 검색 및 나머지 AI 기능은 이 설정으로 켜지지 않는다. 휴가의 주말 선호는 현재 구조화 필드가 없으므로 결과가 이 조건을 보장하지 않는다. 날짜를 직접 확인해야 한다.
- `JHWORKS_PUBLIC_EXPENSE_AI_BUDGET`은 기존 이름을 유지하지만 두 기능이 공유한다. 예산 초과나 불확실한 정산 때 두 기능 모두 제한될 수 있다. 체험 공간당 횟수 역시 두 기능과 두 역할이 공유한다.

## 배포 전 필요한 설정

1. OpenAI API 프로젝트에 해당 모델 접근과 결제 수단을 준비하고, 실제 키는 채팅이나 저장소가 아닌 Secret Manager에 보관한다. Cloud Run 런타임 서비스 계정에 해당 고정 secret version 읽기 권한이 필요하다.
2. 공개 서비스의 프로젝트·리전·DB와 마이그레이션 상태, 기존 예산 원장의 정지/미정산 상태, IAM·트래픽 및 롤백 대상을 확인한다. 기존 데이터나 작업 중인 변경을 덮어쓰지 않는다.
3. Secret Manager 이름과 숫자 버전으로 구성한 JSON 파일과 예산 JSON 파일을 배포 생성기에 전달한다. 두 파일을 모두 지정할 때만 경비와 휴가 AI가 켜진다. 둘 중 하나만 지정하면 생성이 실패한다. 파일에 API 키 원문을 넣지 않는다.

예시 형식(값은 배포 환경에서 확인할 것):

```json
{"name":"YOUR_OPENAI_SECRET_NAME","version":"1"}
```

```json
{"day_micro_usd":500000,"month_micro_usd":2000000,"day_admissions":10,"scope_day_admissions":5,"concurrent_requests":1}
```

예산 예시는 일 $0.50, 월 $2, 전체 일 10회, 공간당 일 5회, 동시 1회다. 최악의 단일 호출 예약액이 약 $0.3072이므로 동시 예약에는 여유가 필요하며, 실제 사용량이 확인되면 정산한다. 네트워크 오류 등 사용량이 불확실할 때는 예약액을 전액 반영한다. 예산 원장 운용 및 복구 절차는 [공개 경비 AI 계약](public-expense-ai-contract.md)을 따른다. 실제 청구 비용은 공급자 청구 및 다른 프로젝트 사용량에 따라 다를 수 있다.

```sh
uv run python -m app.ops.public_demo_manifest \
  --settings /path/to/release-settings.json \
  --api-image IMMUTABLE_API_IMAGE --web-image IMMUTABLE_WEB_IMAGE \
  --commit FULL_COMMIT_SHA --output /path/to/demo-service.json \
  --expense-ai-secret /path/to/secret-reference.json \
  --expense-ai-budget /path/to/ai-budget.json
```

4. 검증된 동일 소스의 API·웹 이미지를 배포하고 `/api/v1/demo/configuration`에서 `approvalDraft`와 `leaveAssistant`가 true인지 확인한다. 새 격리 체험 공간에서 실제 경비 요청→보완→미리보기, 휴가 상담→후속 요청→후보→양식 이동을 확인하고, 예산 한도 및 실패 대응과 원격 로그·사용량도 점검한다. 사용자 검수 이전에 자동 제출되어서는 안 된다.
5. 키와 모델 접근이 없는 경우 유료 provider 호출은 검증되지 않는다. 실제 모델 응답 확인 전까지 활성화 완료라고 표시하지 않는다.
