# A3: 정리 예약과 실패·실행 누락 감지

## 문제와 설계

기존 maintenance Job은 수동 dry-run 기본값이다. 이를 그대로 예약하면 삭제가 일어나지 않고,
같은 Job에 dry-run/apply override를 섞으면 dry-run 성공이 실제 정리의 성공 지표를 가린다.
전용 `jhworks-demo-retention-maintenance` Job을 따로 준비한다. 기존 전용 runtime/DB/session v1,
검증한 이미지 digest, task1/parallelism1/CPU1/512Mi/timeout120/retry0를 재사용한다.
처음에는 새 Job도 dry-run으로 생성하고 예약·알림 도달 검증 후 동일 Job의 명시적 apply 설정으로 전환한다.

작업 묶음은 새 Job의 dry-run/apply manifest, OAuth Scheduler 생성 payload, Job 범위 IAM binding,
기본 disabled인 실패·성공 누락 alert policy 두 개다. 생성기는 로컬 파일만 쓰며 외부 API를 호출하지 않는다.
Scheduler는 매시17분 UTC, body `{}`, retry0, 요청 deadline30초다. 호출 계정은 해당 Job의
`roles/run.invoker`만 가지며 override·Secret·DB·프로젝트 공통 역할을 주지 않는다.
Scheduler 생성 state는 output-only이므로 PAUSED 생성으로 가정하지 않는다. 최초 대상이 dry-run인 상태에서
생성 후 즉시 pause하고 실제 state를 조회한다. 이 사이 실행될 수 있는 것도 dry-run이어야 한다.

성공 누락은 `run.googleapis.com/job/completed_execution_count`의 **succeeded** 결과만3시간 합산한다.
0 샘플만 계속 오는 경우와 시계열 자체가 없는 경우 모두1 미만이면 감지한다. 지표가 한 번도 없던
Job도 빈 벡터를0으로 처리한다. 단순 metric-absence는 값0과 실행 성공을 구분하지 못하므로 사용하지 않는다.
실패는 같은 Job의 succeeded 이외 완료 결과가 최근10분에1개 이상이면 감지한다.
PromQL은 project/location/job/monitored_resource를 모두 고정하고 두 정책은 별도 incident를 만든다.
평가는60초, pending60초이며 지표 수집·전파 지연이 추가된다. Scheduler HTTP200은 성공 완료가 아니다.

## 단계와 적용 gate

1. 고정 소스 CI/자체 리뷰/병합, 현재 Job·digest·전용 Secret 참조·새 자원 이름 충돌·채널을 읽기 확인한다.
2. 아래 새 API/계정/Job/IAM/예약·알림/비용/자동 삭제 범위를 검토하고 사용자 확인을 받는다.
3. Scheduler API와 service agent를 준비하고 전용 호출 SA를 만든다. 관리 키는 만들지 않는다.
   새 retention Job을 **dry-run** manifest로 생성하고 Job에만 invoker를 부여한다.
4. disabled alert policy를 만들고 승인된 수신 채널을 연결한다. 실제 쿼리를 Monitoring에서 조회한다.
   새 Job 성공 실행1회와 JSON dryRun=true/stage=complete/steps 및 Cloud Run 종료 상태를 함께 확인한다.
5. Scheduler 생성→즉시 pause→state/target/OAuth/body/retry 조회, 승인된 수동 trigger1회로 접수/완료를 대조한다.
6. 실패 알림은 새 Job의 일회성 실행 override로 `python -c 'raise SystemExit(1)'`만 실행해 검증한다.
   DB/Secret을 읽는 앱을 실행하지 않는다. 기존 env 참조를 가진 컨테이너의 시작은 일어나므로 이를 자격증명 사용0으로
   단정하지 않는다. 기본 Job command는 바꾸지 않고 Scheduler 호출 SA에 override 권한을 주지 않는다.
7. 누락 알림은 Scheduler pause 상태에서 최근 성공이3시간 이상 지난 뒤 실제 incident·수신을 확인한다.
   시간을 줄여 실험한 결과는 실제3시간 조건 검증과 구분한다. 실패/누락 두 incident/수신 시각을 각각 기록한다.
8. 최신 dry-run 대상/피드백/백업·private 보존 대조를 확인한다. 실제 삭제 범위가 바뀌면 다시 확인한다.
   명시적 apply manifest 적용 후 신규 성공1회/JSON dryRun=false/삭제건수/보존을 확인한다.
   활성화 이전 dry-run 성공은3시간 이내라면 누락 지표에 남으므로 이 첫 apply 성공을 생략하지 않는다.
9. 정상 정책 enabled와 채널·수신 검증 후 Scheduler resume, 다음 자연 예약 완료/앱 JSON/보존·누적 처리량 확인.
   이 증거 전에는 A3 완료 또는 운영 보관 정책 준수로 표시하지 않는다.

기존 DB gate/행 잠금이 중복 invocation을 처리한다. task/parallelism1은 **여러 execution 사이**의
동시 실행을 막지 않는다. 상태 미확정/시간 초과 시 자동 재실행하지 않고 실행 목록·로그를 먼저 대조한다.
피드백은 먼저 별도 commit되므로 workspace 실패 때 feedback만 이미 정리됐을 수 있다.

## 복구와 처리량

- 실패/누락 알림: Scheduler pause 후 running execution·마지막 완전 성공·앱 단계/건수·DB 상태를 읽는다.
  HTTP 접수만으로 재실행하지 않고 이전 execution의 종료/부분 commit을 확인한다.
- 장애가 해소되면 기존 수동 dry-run으로 예상 정리 건수/관계를 확인한 후 승인 범위에서1회 apply한다.
  기본 설정/다음 예약을 확인하고 재실행0 및 정상 예약1회를 기록한다.
- 중단: Scheduler pause/state 확인→진행 중 execution 확인. pause는 이미 시작한 execution을 취소하지 않는다.
  필요 시 별도 판단으로 cancel한다. 자동 복원/원본 DB 덮어쓰기는 하지 않는다.
- 시간당 batch5는 이론상120공간/일, 생성20/일보다 크지만 잠금·관계 거부·장애·UTC 몰림을 포함한 보장은 아니다.
  retained30/만료+24h 조합은 정상 운영 중에도 UTC 경계 유입으로 포화될 수 있다. 상한/보존기간은 바꾸지 않으며
  거부 안내/회복 시각 검증은 A4에서 확인한다. 피드백30일 보존도 실제 실행 성공·장애 대응 증거가 필요하다.

## 외부 변경 범위

프로젝트 `jhworks-staging-tykimdream`, region `asia-northeast3`에 한정한다.
새 Scheduler API/service agent, 호출 SA `jhworks-demo-scheduler`, retention Job1,
해당 Job invoker binding1, Scheduler1, disabled alert policy2와 승인된 알림 채널을 준비한다.
운영자에게 이미 없는 actAs/create 권한이 필요하면 그 구체적 범위를 다시 확인하며 owner/editor를 추가하지 않는다.
기존 private 서비스/IAM·준비 도메인·업무 데이터·새 Secret/키 버전은 변경하지 않는다.
자동 apply는 만료24h 합성 공간 batch5와 만료30일 피드백을 실제 삭제하며, 활성화 전 대상/복원 근거를 확인한다.

이 문서는 적용 전 계획이다. 실제 자원 생성·예약·알림 도달·자동 삭제는 결과 기록이 생기기 전까지 미완료다.

## 2026-10-23 사전 조회와 검증

읽기 전용 조회로 기존 `jhworks-demo-maintenance`의 dry-run/batch5·task1/parallelism1·CPU1/512Mi·
120초/retry0, 전용 demo runtime/DB/session v1을 확인했다. 고정 이미지 참조는
`asia-northeast3-docker.pkg.dev/jhworks-staging-tykimdream/jhworks/api@sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0`다.
새 Job 적용 전에는 이 digest와 기존 execution의 child digest/source 관계도 다시 확인한다.
Scheduler API 비활성, Monitoring/Logging 활성, 알림 채널0·정책0을 조회했다.
기존 Job의24시간 완료 지표는 `result=succeeded`/합계5를 반환했다. 이것을 새로운 실행 증거로 표현하지 않는다.
Secret payload·DB·새 실행·자원 변경에는 접근하지 않았다. 기존 access token은 메모리에서만 사용했다.

21:05:59 KST의 실제 Monitoring PromQL read-only 대조4개도 통과했다. 실행 이력 없는 새 Job/0 샘플
대조는 비정상 벡터를 반환하고, 기존 성공24시간 창/양수 대조는 빈 벡터로 정상 판별했다.
비교 연산에 `bool`을 쓰지 않는다. 비정상 결과의 값이0이어도 벡터가 존재하면 alert 조건이 성립한다.
`~/jhworks-retention-monitoring-preflight-20261023.json`을0600/exclusive로 저장했다.
cloudWrites0/secretPayloadsRead0/alertDeliveryTested=false다. 정책 생성·incident·메일 수신 실험은 아직 아니다.

생성 명령(네트워크/자격증명 접근 없이7개 JSON 출력):

```sh
cd apps/api
uv run --frozen python -m app.ops.demo_retention_operations \
  --api-image asia-northeast3-docker.pkg.dev/jhworks-staging-tykimdream/jhworks/api@sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0 \
  --output-dir ../../artifacts/cloud-run/retention-operations-20261023
```

생성한 디렉터리는 재실행으로 덮어쓰지 않는다. 실제 채널 생성/검증 뒤 같은 프로젝트의 숫자 resource name을
`--notification-channel projects/.../notificationChannels/숫자ID`로 넘겨 **새 디렉터리**에 재생성한다.
이메일/토큰/비밀값을 설정 파일이나 공개 저장소에 넣지 않는다. 채널 미지정 결과는
`notificationChannelConfigured=false`인 preview이며 활성화 가능한 운영 상태가 아니다.

전용 회귀13개와 전체 API490 passed/29 PostgreSQL skipped(로컬 DB 미실행),
Ruff app/tests/alembic·strict mypy163파일 통과. 권한 범위·private/demo Secret 혼용·mutable/외부 image·
채널 injection·offline 실행·기존 파일 보존·정책 기본 비활성·누락0/빈 시계열 조건을 검사한다.
로컬 테스트만으로 Google 정책 생성/알림 도달을 입증하지 않는다.

## 비용과 첫 적용 승인 단위

첫 적용은 **dry-run 기반 시설과 알림 검증**이다. Scheduler API/service agent·호출 SA·새 dry-run Job·
Job invoker binding·Scheduler 생성 후 pause·알림 정책2/수신 채널 연결·검증 실행 최대6회(수동 명령 기준)를
검토한다. 자동 apply/resume·실제 삭제·private 변경은 이 승인에 포함하지 않는다.
Scheduler 생성과 pause 사이/중복 전송으로 추가 invocation이 가능하므로 dry-run을 먼저 보장한다.
관리 키/새 Secret version은 만들지 않는다. 수신 주소는 사용자 선택 후 실제 채널에만 설정한다.

2026-10-23 공식 가격표 재확인: Scheduler는 계정 전체3 Job 무료 이후 Job당$0.10/31일이며
paused도 집계된다. 서울 Jobs 기본 단가 CPU $0.0000216/vCPU초·RAM $0.0000024/GiB초를 사용하면
CPU1/512Mi에서 실행당60~120초는 약$0.00137~$0.00274,6회는 약$0.0082~$0.0164다.
이는 task 실행 시간 계획이며 instance 시작/종료·추가 invocation·로그/전송·환율/세금을 포함하지 않는다.
무료 잔여는 계정 전체 공유이므로 무과금을 보장하지 않는다. 우선 정지한 Scheduler의 월 비용과
검증 실행량을 승인받고, 자동 정리 활성화 직전에 실제 실행시간/무료잔여/백업을 다시 대조한다.

후속 자동 운영은 매시1회/31일744회로 동일60~120초 가정의 compute 약$1.02~$2.04 + Scheduler
최대$0.10/월(무료 적용 전, 위 부대 항목 제외)이다. timeout은 instance 총 과금의 상한이 아니다.
현재 공지상 metric alerting 과금은2027-09-01보다 일찍 시작하지 않으며, 이후3 metric reference의
기본료/조회 포인트 비용을 재검토한다. 기존 시스템 지표를 사용하고 새 custom/log-based metric은 만들지 않는다.

공식 근거: [Cloud Run 예약/OAuth/IAM](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule),
[완료 지표](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z),
[PromQL 정책](https://docs.cloud.google.com/monitoring/promql/create-promql-alerts),
[PromQL 매핑](https://docs.cloud.google.com/monitoring/promql),
[Scheduler 가격](https://cloud.google.com/scheduler/pricing), [Run 가격](https://cloud.google.com/run/pricing),
[Observability 가격](https://cloud.google.com/products/observability/pricing).
