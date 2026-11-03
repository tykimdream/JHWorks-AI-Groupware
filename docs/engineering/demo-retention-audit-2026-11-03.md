# 보관 운영 읽기 대조 — 2026-11-03

2026-11-03 약 12:32 KST에 Google Cloud 콘솔에서 프로젝트 `jhworks-staging-tykimdream`, 리전 `asia-northeast3`의 보관 운영을 읽기 전용으로 확인했다. 이전의 [2026-10-25 점검](demo-retention-current-audit-2026-10-25.md)을 대체하는 현재 관찰이며 자동 정리 가동이나 실제 보관 정책 준수를 입증하지 않는다.

- Monitoring에는 `JHWorks demo retention: no successful completion for 3 hours`의 [열린 incident](https://console.cloud.google.com/monitoring/alerting/alerts/0.oejnjr9neinv?project=jhworks-staging-tykimdream)가 1건 있었고, 시작은 2026-11-02 22:19:10 KST로 표시됐다. 동일 정책의 이전 incident가 닫혔다는 메일은 이 새 열린 incident의 복구를 뜻하지 않는다. 두 보관 알림 정책은 사용으로 표시됐다.
- [Cloud Run Job 실행 기록](https://console.cloud.google.com/run/jobs/details/asia-northeast3/jhworks-demo-retention-maintenance/executions?project=jhworks-staging-tykimdream)에는 10월 23일의 성공 3건과 실패 1건이 표시됐으며 가장 최근 성공 종료 시각은 21:47:22 KST였다. 실패 건은 이전 테스트 이력이고 이 화면만으로 새 장애 원인이나 데이터 삭제 여부를 판단할 수 없다.
- 2026-10-25에 Scheduler PAUSED로 조회된 과거 기록은 있다. 이번 Cloud Shell `gcloud scheduler jobs describe`는 활성 계정이 없어 거절됐고, Scheduler 콘솔 목록도 로드되지 않아 **현재 Scheduler state는 미확인**이다. Cloud Run의 트리거 화면은 트리거 없음으로 표시했으나 이를 별도 Scheduler 자원의 부재나 정지 증거로 사용하지 않는다.
- Job 실행·Scheduler 재개·알림 변경·DB 조회·삭제·배포는 하지 않았다. 다음은 인증된 읽기 전용 경로에서 Scheduler 상태/대상과 실행·앱 로그를 확인하고, 현재 열린 incident의 원인을 대조하는 것이다. 자동 운영 전환이나 실제 정리는 기존 [운영 절차](demo-retention-operations.md)의 별도 적용 조건을 충족해야 한다.

## 2026-11-03 반복 알림 조정

약 12:35 KST Scheduler 콘솔을 다시 열어 `jhworks-demo-retention-hourly`가 **Paused**, 대상이 위 보관 Job임을 확인했다. 이 상태에서 성공 누락 정책이 3시간마다 실행 성공을 기대해 일시정지와 충돌한다. 사용자가 반복 메일 해결을 요청해 성공 누락 정책 `8585053121123571518`만 사용 중지하고 콘솔의 disabled 상태를 확인했다. 기존 실행 실패 정책 `16397418724392454572`는 enabled를 유지한다. Job·Scheduler·데이터는 변경하지 않았다.

변경 직후 기존 incident `0.oejnjr9neinv`는 여전히 열려 있었으며 수동으로 닫지 않았다. 정책 비활성 상태의 메일 중단이나 incident 자동 종료는 아직 관찰하지 못했다. **정기 운영을 재개할 때는 성공 누락 감시를 다시 활성화하고 첫 실제 실행·앱 JSON·수신을 검증해야 한다.** 현재 누락 감시가 꺼져 있으므로 Scheduler를 별도로 재개해도 실행 누락 메일은 발생하지 않는다. 실제 보관·삭제 운영은 계속 미완료다.
