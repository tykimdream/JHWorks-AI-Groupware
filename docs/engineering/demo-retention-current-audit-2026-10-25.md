# 최소 정리 운영의 현재 상태 대조 — M1-01

관찰 시각: 2026-10-25 03:06:42 UTC / 12:06:42 KST.
앱 내부 Cloud Shell의 기존 인증 계정으로 Job·Scheduler·최근 실행·기존 알림 정책을 **읽기만** 했다.
리소스 변경0·새 Job 실행0·Secret payload 접근0이며 DB 접속/행 수 조회는 수행하지 않았다.

## 실제 조회와 기존 기록의 차이

| 항목 | 현재 조회 | 판단 |
| --- | --- | --- |
| 정리 Job | jhworks-demo-retention-maintenance, maintenance module, batch5, apply 인자 없음 | dry-run 설정 유지. 실제 정리 운영 아님 |
| 실행 상한 | task1/parallelism1/timeout120초/retry0 | 기존 제한 유지 |
| 이미지 | sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0 | 고정 digest. 최신 제품 source/새 migration과의 호환성은 별도 확인 |
| Scheduler | jhworks-demo-retention-hourly, PAUSED, 매시17분 UTC, retry0 | 자동 예약 정리 비활성 유지 |
| 실패·누락 정책 | 기존 두 정책 모두 enabled, 각각 channel1 | 설정 존재 확인. 현재 incident/이메일 도달을 새로 시험한 것은 아님 |
| 최근 실행 | 2026-10-23 성공3·실패1, 마지막 성공12:47:22 UTC | 기존 실행4건. 이번에 새로 실행한 결과가 아님 |
| 만료/보존 공간 수 | 미조회 | 실제 apply 전 새 preflight가 필요 |
| 백업 신선도/현재 복원 가능성 | 미조회 | 기존 복원 증거를 새 백업으로 표시하지 않음 |

`completed`는 조회 보고서에서 Completed condition=True인지 계산한 값이다.
실패 실행에도 completionTime이 있으며, completed=false를 아직 실행 중이라는 뜻으로 사용하지 않는다.

## 보관한 증거

Cloud Shell: `~/jhworks-retention-readonly/20261025T030642Z.json` (0700 디렉터리/0600 파일).
로컬 ignored 사본: `artifacts/cloud-run/retention-current-audit.json`.
보고서는 값 없는 Secret 참조조차 출력하지 않으며 토큰·이메일·DB URL·정책 채널 주소·개인 자료를 포함하지 않는다.
Git에는 상태 대조와 관찰 시각·실행 식별자만 기록한다.

최근 실행:

- nrtks: 2026-10-23 12:35:52 UTC, succeeded1/failed0.
- v7stw: 2026-10-23 12:43:50 UTC, succeeded1/failed0.
- 7fq24: 2026-10-23 12:45:46 UTC, succeeded0/failed1.
- 6fgg5: 2026-10-23 12:47:22 UTC, succeeded1/failed0.

설정의 존재와 실행 성공만으로 앱 JSON의 dry-run/apply 결과·보존 검증·알림 도달까지 확대 해석하지 않는다.
기존 앱 결과 대조는 [정리 리허설](demo-retention-rehearsal.md),
적용 조건은 [기존 운영 계약](demo-retention-operations.md)을 따른다.

## M1-02에 남는 구체적 범위

1. 실제 적용할 소스·이미지와 현행 DB schema 호환, 전용 runtime/권한과 대상 경계를 재대조한다.
2. 실제 만료/보존 대상 수와 첫 batch5의 계획·백업/복구 참조를 현재 시점에 확인한다.
3. 기존 승인의 한계를 대조한 뒤 실제 apply/지속 예약이 필요한 구체적 변경만 준비한다.
   이번 조회를 실제 삭제·예약 재개 승인으로 사용하지 않는다.
4. 적용 후 보존 대상 유지·재실행의 중복 삭제 없음·다음 체험 가능성을 확인한다.
   예약 운영을 켠 경우 자연 실행 결과는 별도 증거로 남긴다.

새 Job/계정/알림 채널·정책을 만들거나 과거의 장시간 누락·실패 실험을 반복하는 작업은 추가하지 않는다.
이 대조로 M1-01의 기반·남은 차이를 기록했으며 M1-02의 실제 운영 마감은 미완료다.
다음 개발은 M2-02의 서버 capability·예산으로 진행할 수 있다.
