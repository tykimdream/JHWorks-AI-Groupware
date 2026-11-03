# 보관 운영 읽기 대조 — 2026-11-03

2026-11-03 약 12:32 KST에 Google Cloud 콘솔에서 프로젝트 `jhworks-staging-tykimdream`, 리전 `asia-northeast3`의 보관 운영을 읽기 전용으로 확인했다. 이전의 [2026-10-25 점검](demo-retention-current-audit-2026-10-25.md)을 대체하는 현재 관찰이며 자동 정리 가동이나 실제 보관 정책 준수를 입증하지 않는다.

- Monitoring에는 `JHWorks demo retention: no successful completion for 3 hours`의 [열린 incident](https://console.cloud.google.com/monitoring/alerting/alerts/0.oejnjr9neinv?project=jhworks-staging-tykimdream)가 1건 있었고, 시작은 2026-11-02 22:19:10 KST로 표시됐다. 동일 정책의 이전 incident가 닫혔다는 메일은 이 새 열린 incident의 복구를 뜻하지 않는다. 두 보관 알림 정책은 사용으로 표시됐다.
- [Cloud Run Job 실행 기록](https://console.cloud.google.com/run/jobs/details/asia-northeast3/jhworks-demo-retention-maintenance/executions?project=jhworks-staging-tykimdream)에는 10월 23일의 성공 3건과 실패 1건이 표시됐으며 가장 최근 성공 종료 시각은 21:47:22 KST였다. 실패 건은 이전 테스트 이력이고 이 화면만으로 새 장애 원인이나 데이터 삭제 여부를 판단할 수 없다.
- 2026-10-25에 Scheduler PAUSED로 조회된 과거 기록은 있다. 이번 Cloud Shell `gcloud scheduler jobs describe`는 활성 계정이 없어 거절됐고, Scheduler 콘솔 목록도 로드되지 않아 **현재 Scheduler state는 미확인**이다. Cloud Run의 트리거 화면은 트리거 없음으로 표시했으나 이를 별도 Scheduler 자원의 부재나 정지 증거로 사용하지 않는다.
- Job 실행·Scheduler 재개·알림 변경·DB 조회·삭제·배포는 하지 않았다. 다음은 인증된 읽기 전용 경로에서 Scheduler 상태/대상과 실행·앱 로그를 확인하고, 현재 열린 incident의 원인을 대조하는 것이다. 자동 운영 전환이나 실제 정리는 기존 [운영 절차](demo-retention-operations.md)의 별도 적용 조건을 충족해야 한다.
