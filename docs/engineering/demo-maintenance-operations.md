# 전용 데모 예약·실패/누락 알림 — offline 준비

환경 전환 재개 순서는 [인계 문서](handoff-20261023.md)를 먼저 따른다.

## 문제와 선택

수동 정리1/재실행0이 성공해도 이후 운영자가 실행하지 않으면 workspace가 쌓이고 피드백30일
보관 안내를 지키기 어렵다. 웹 내부 timer는 min=0에서 실행을 보장하지 않는다.
GitHub schedule은 지연/누락과 장기 무활동 중단이 있어 보관 작업의 유일한 주기로 선택하지 않는다.
기존 private Job과 DB 원자 정리/timeout/관계 검증을 재사용하고 Cloud Scheduler1개와
Cloud Run 기본 지표의 Monitoring 알림2개로 시작한다. 새 worker/Redis/큐/custom metric은 도입하지 않는다.

2026-10-23 실제 읽기 검사: Scheduler API off, Monitoring API on, notificationChannels0.
수신 대상은 사용자가 현재 GCP 로그인 계정 이메일을 선택했다. 이메일 원문은 공개 설정/문서에 넣지 않는다.
이 선택은 자원/채널/IAM 생성이나 자동 정리 활성화 승인이 아니다.

## 구현한 offline 계약

`app.ops.demo_maintenance_schedule`은 JSON 파일5개만 만든다. SDK/subprocess/network를 호출하지 않는다.
설정은 기존 MaintenanceSettings를 재사용하고 서울의 고정 demo Job/전용 runtime/DB·session v1만 허용한다.
private staging/migration Secret·다른 버전/프로젝트 notification channel·임의 분당 cron/호출 계정은 거부한다.
잘못된 profile은 폴더 생성 전에 실패하고, 이전 plan 폴더를 덮어쓰지 않는다.

- Scheduler: 매시17분/Etc UTC, retryCount0/maxRetryDuration0, HTTP 접수 deadline60초.
  Google Run v2의 해당 Job `:run`으로 POST `{}`만 보내며 명령/환경변수 override는 없다.
  이60초는 비동기 실행 요청 시간이며 Job의120초 timeout과 다르다.
- 새 `jhworks-demo-scheduler`는 해당 Job의 run.invoker binding만 갖는 안이다.
  runtime/기본 compute 계정을 호출자로 재사용하지 않고 Secret/DB·actAs·runWithOverrides·키 발급을 주지 않는다.
  OAuth cloud-platform scope를 사용해도 IAM 권한이 그 Job 호출로 제한된다. binding fragment를 프로젝트나
  전체 IAM policy의 대체 파일로 적용하지 않는다.
- 실패 초안: 그 project/location/job의 completed_execution_count 중 result=failed가 0보다 큼.
- 누락 초안: 성공 시계열3시간 없음 OR 3시간 성공 합계가1 미만. 새 샘플이 계속0이면 metric absence만으로는
  잡히지 않으므로 두 조건을 나눈다. 누락 alert의 autoClose는1일로3시간 탐지 창보다 길다.
- 알림은 채널이 있어도 항상 enabled=false로 만든다. 채널 null은 아직 연결하지 않았다는 뜻이다.
  네이티브 result label/샘플·정렬·누락 평가와 실제 알림 도달은 적용 후 별도 검증해야 한다.
  운영자가 처음 한 번도 실행하지 않아 시계열이 없는 문제를 피하려면 성공 seed를 확인한 뒤 활성화한다.

```sh
cd apps/api
uv run python -m app.ops.demo_maintenance_schedule \
  --settings ../../deploy/cloud-run/maintenance-operations.example.json \
  --output ../../artifacts/cloud-run/maintenance-operations-draft
```

예시는 replace-project/null 채널이다. 실제 프로젝트로 바꿔도 이 명령은 외부 설정을 적용하지 않는다.
출력은 scheduler create payload, Job 전용 IAM binding fragment, disabled alert2개, 적용 gate 계획이다.
`state: PAUSED`를 create payload에 쓰지 않는다. Scheduler state는 output-only이므로 raw create는
schedule에 따라 즉시 실행될 수 있다. 반드시 기존 Job의 기본 dry-run을 유지한 채 생성하고 pause·상태 조회를
확인한다. 아직 정상 기본 Job은 dry-run/batch5이며 바꾸지 않았다.

## 실제 적용 전 gate와 검증

1. 정확한 head CI/자체 리뷰/병합 → 실제 계정/Job/spec/Secret v1/default dry-run·backup을 재확인.
2. Scheduler API/service agent, 호출 SA1/해당 Job binding, Scheduler1, 이메일 채널1, disabled policy2의
   구체적 비용·권한·수신 대상을 제시하고 승인. 아직 이 자원/권한을 만들지 않았다.
3. dry-run 대상 생성→즉시 pause/조회→수동 Scheduler 요청1회와 비동기 Job의 결과를 별도로 확인.
   Scheduler HTTP200은 정리 성공이 아니다. retry0도 중복 delivery 가능성을 제거하지 않으므로 DB 재실행
   계약이 필요하다. 기존 Cloud Run Job 자체 retry0/120초/CPU1·512MiB 제한도 재확인한다.
4. 현재 native metric label·sample/지연을 읽어 초안을 검증하고 채널 수신을 확인한다.
   실패·누락 drill은 별도 구체적 실행/비용 범위 확인 후 수행한다. 누락 창을 짧게 한 실험을 실제3시간
   장애 실적으로 표현하지 않는다. incident 자동 종료와 업무 복구도 구분한다.
5. 위 검증 뒤에만 자동 삭제 범위·월 예산을 승인받고 paused 상태에서 Job의 고정 apply 인자를 적용한다.
   예산 알림은 과금 차단이 아니다. Scheduler resume/첫 주기 완료/알림 복구까지 확인해야 운영 완료다.

현재 앱/DB/public IAM/DNS/기존 Job/Secret을 바꾸지 않았다. 이메일 채널도 아직 없다.
기존 수동 리허설의 공간2/결재1/피드백1/공용3·10·48은 유지한다.

로컬 최종 관련23 passed/0.15초, Ruff와 strict mypy159 source files, example CLI 파일5개 생성/
cloudOperations0을 확인했다. 최종 head의 전체 CI와 provider의 실제 적용/알림 검증은 별도다.

## 비용 재검토 — 2026-10-23 공식 문서 기준

Scheduler는 결제 계정 첫3 Job/월 무료이고 초과1개는 $0.10/31일, paused도 집계된다.
매시1회·31일은744회다. Job당 최소1분이므로 기본 계획은44,640 vCPU초/22,320 GiB초이고,
각2분이면 두 배다. 기동/종료·중복 호출/장애·Secret 접근·로그/전송/세금과 공유 무료 할당에 따라 달라진다.
현재 약8초 리허설을 월744×8초 과금으로 계산하지 않는다. 실제 생성 직전에 리전 단가·잔여 할당을 재확인한다.

Cloud Run 기본 지표 ingestion은 비과금 범위다. Monitoring API time-series 읽기는 계정 첫100만 시계열/월 후
$0.50/100만이며 다른 read API는 비과금이다. 별도 custom log metric/유료 synthetic monitor를 만들지 않는다.
현재 공식표의 alerting 요금 적용일은 2027-09-01이며, 그때는 metric reference당 월$0.35와 query points
비용이 예정돼 있다. 이 초안은 실패1+누락2=3 references이므로 예정 기본분은 월$1.05다.
미래 요금·정책은 적용/장기 운영 전에 다시 확인하며 현재 청구액이나 무과금 보장으로 표현하지 않는다.

근거: [Run 예약/OAuth](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule),
[Scheduler resource/state/retry](https://docs.cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs),
[Scheduler 가격](https://cloud.google.com/scheduler/pricing), [Run 가격](https://cloud.google.com/run/pricing),
[native metric](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z#run),
[AlertPolicy REST](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies),
[Observability 가격](https://cloud.google.com/products/observability/pricing).

학습/면접: 왜 요청 접수와 작업 완료를 분리하는가, retry0인데도 멱등성이 왜 필요한가,
0 sample과 no sample은 왜 다른가, disabled 설정 파일과 실제 수신/복구 실험은 왜 다른 증거인가를
현재 runner·native counter·고정 manifest로 설명한다.
