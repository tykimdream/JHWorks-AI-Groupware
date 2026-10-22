# 공개 전 보관 정리 실행 경로

## 문제와 완료 조건

보관 정리 서비스/CLI가 있어도 운영자가 매번 실행하지 않으면 만료 공간이 쌓여 체험 총량에 도달하고,
피드백 보관 안내를 지킬 수 없다. 기존 30개 retained workspace, 하루 신규 20개 제한을 유지한다.
정리·재실행·부분 실패·DB 잠금 대기와 종료 코드를 검증하고, 네트워크 없이 검토할 Job 설정을 만든다.
실제 예약/실패 감지/공개 활성화는 외부 적용 증거를 별도로 남겨야 완료다.

## 대안과 선택

| 대안 | 판단 |
| --- | --- |
| 수동 CLI | 복구 경로로 유지. 일상 보관 정책의 유일한 수단으로 사용하지 않음 |
| Cloud Run 서비스 안 timer | min=0/인스턴스 종료·증가 시 누락/중복. 상시 CPU 지출도 불필요 |
| GitHub schedule | GCP Scheduler 없이 실행 가능하지만 지연/누락·공개 저장소 60일 무활동 중단이 있어 보관 작업의 유일한 주기로 선택하지 않음 |
| Cloud Scheduler → private Cloud Run Job | 우선 적용 후보. 기존 이미지·DB 정리 함수를 재사용하며 서비스 공개 없이 실행 가능. 새 자원/권한/과금은 적용 전 승인 |

새 Redis/큐/worker framework나 업무 테이블 migration은 도입하지 않는다.

## 구현

`python -m app.ops.demo_maintenance`는 기본 dry-run이다. 공개 데모 전용 설정/AI=false를 요구한다.
worker의 PUBLIC_DEMO_ENABLED는 이 프로세스에서만 적용되며 HTTP 서비스 공개 설정을 바꾸지 않는다.
피드백 정리를 먼저 실행하고, 다음 새 Session에서 만료 24시간 이상인 workspace를 최대 5개 정리한다.
피드백은 30일 경계, 기존 gate/실제 삭제 RETURNING을 재사용한다. workspace는 관리 namespace·관계
검증을 통과한 그래프만 기존 순서대로 삭제하며 일반 private 직원/업무나 생성 일일 예산은 지우지 않는다.

두 단계는 각각 commit한다. workspace 단계 실패 시 이미 완료된 피드백 정리는 되돌아가지 않는다.
최종 JSON은 completed steps/실패 stage/errorType/ERROR severity를 남기고 CLI는 1로 종료한다.
재실행 때 이미 정리한 항목은 0건이 된다. 예외 원문·비밀번호·의견 본문은 출력하지 않는다.
PostgreSQL 트랜잭션마다 statement_timeout=15초, lock_timeout=5초를 설정한다.
Job 자체 timeout은 120초이며 강제 종료 시 마지막 JSON이 없을 수 있어 Cloud Run 실행 결과도 봐야 한다.
설정 검증이 초기 DB/model import에서 실행되는 경우도 JSON 오류 경계 안으로 옮겼다.
잘못된 production 설정을 별도 Python 프로세스로 실행하는 회귀는 수정 전 1 failed(JSON 없음),
수정 후 passed였다. stdout의 안전한 오류 유형과 빈 stderr를 확인하며 합성 비밀 값이 출력되지 않는다.

offline generator는 고정 image digest, 같은 project/region, 숫자 Secret 버전만 받는다.
Job 1 task/parallelism 1, CPU 1/512MiB, retry=0, runtime 계정·runtime DB/session Secret 참조만 생성한다.
기본 manifest에는 --apply가 없다. migration 계정/DB Secret이나 AI key를 추가하지 않는다.
`https://maintenance.invalid`는 production 설정 검증을 위한 예약 origin이며 worker는 HTTP를 열지 않는다.

```sh
cd apps/api
uv run pytest tests/test_demo_maintenance.py tests/test_demo_maintenance_manifest.py -o addopts= -q
uv run python -m app.ops.demo_maintenance_manifest \
  --settings ../../deploy/cloud-run/maintenance.example.json \
  --api-image 'asia-northeast3-docker.pkg.dev/replace-project/jhworks/api@sha256:<검증된 64자리 digest>' \
  --output ../../artifacts/cloud-run/demo-maintenance-dry-run.json
```

예시는 placeholder이므로 실제 실행 전 project/digest를 교체한다. 이 명령은 파일만 만들며 gcloud를 실행하지 않는다.
로컬 전체 API 402 passed/21 skipped (37.14초), 신규 관련 16 passed, Ruff와 strict mypy149 files 통과.
추가 PostgreSQL 회귀는 실제 Job runner의 정리/재실행/private 행 보존 및 실제 timeout 설정을 검사한다.
해당 PostgreSQL 실행은 별도 CI로 확인하며 로컬 skip을 통과로 표시하지 않는다.

## 외부 적용 순서와 승인 경계

1. PR의 정확한 head CI/리뷰/병합 → 기존 private release로 runner를 포함한 immutable image 확보.
2. 검토한 Job manifest와 실제 project/계정/Secret 참조·비용을 사용자에게 제시.
3. 승인 후 전용 private Job 생성 및 **dry-run** 실제 실행. 기존 private 앱/DB 공개 전환은 하지 않음.
4. 실제 종료 상태/JSON/no-op 재실행과 실패 감지를 확인한다. 외부 데이터 삭제 실험은 별도 승인 또는
   명시적으로 폐기 가능한 합성 fixture 범위를 지정한 승인 후 진행한다.
5. Scheduler 호출 계정에는 해당 Job의 run.invoker만 부여하고 Secret/DB 권한을 주지 않는다.
   API service agent·새 계정/Job·권한·자동 삭제 적용은 승인 전 만들거나 활성화하지 않는다.
6. 매시 17분 실행을 후보로 한다. 정리 처리량 최대 120 workspace/일은 신규 상한20/일보다 크다.
   중복 invocation은 발생할 수 있으므로 DB gate/SKIP LOCKED와 재실행 계약을 유지한다.
7. Scheduler HTTP 성공은 비동기 실행 요청의 접수일 뿐 정리 성공이 아니다. Cloud Run failed execution과
   일정 기간 성공 실행 없음도 감지하고 알림 도달을 실험한 후에만 공개 수집을 켠다.

Cloud Scheduler Job의 state는 output-only다. 생성 payload에 PAUSED를 적으면 안전하게 비활성 생성된다고
가정하지 않는다. 초기에는 dry-run Job만 대상으로 검증하고, 별도 pause 조회/실행 모드 확인 후 적용한다.
장기 장애로 30일 보관 안내를 초과하지 않도록 운영 여유/대응 절차를 확정해야 하며 예약 코드만으로
보관 정책 준수를 보증하지 않는다. 현재 실제 Scheduler·Job·자동 삭제는 없다.

## 비용과 근거 (2026-10-22 공식 문서 확인)

Cloud Scheduler는 결제 계정 전체 첫 3 Job/월 무료, 초과 Job은 $0.10/31일이다. paused도 집계된다.
Cloud Run Jobs는 instance 기반, 실행당 최소 1분 과금이다. 매시 1회·31일·각1~2분이면
44,640~89,280 vCPU초와 22,320~44,640 GiB초의 실행량 계획이다. timeout 전후 준비/종료·중복호출은
이 단순 추정에 추가될 수 있고, 실제 런타임을 측정해야 한다. 무료 할당은 계정의 다른 사용과 공유한다.
서울 단가·무료 잔여·로그/전송·환율/세금을 적용해 외부 생성 직전에 금액을 다시 제시한다.
무료 할당 내 예상이라도 무과금 보장이나 과금 차단이라고 표현하지 않는다.

공식 근거: [Jobs 과금](https://cloud.google.com/run/pricing),
[Scheduler 과금](https://cloud.google.com/scheduler/pricing),
[Jobs 예약/OAuth 호출](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule),
[Scheduler state 계약](https://docs.cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs),
[GitHub schedule 제약](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

학습/면접: 왜 웹 프로세스 timer가 min=0에서 안전하지 않은지, 왜 요청 접수와 작업 완료를 구분하는지,
한 단계 commit 뒤 다음 단계가 실패하면 재시도 결과를 어떻게 해석하는지 현재 runner로 설명해본다.
