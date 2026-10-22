# 방문자·피드백 코드의 비공개 배포 검증

2026-10-22 실행. 공개 데모 운영 검증이나 실제 의견 수집과 구분한다.

## 실제 배포

- 앱 commit `5342bd4f8acc82ee51aa47fd4129b5c516f84571` (#43 병합).
- [main CI 39764503071](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39764503071) 성공 후
  [private release 39765860506](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39765860506) 성공.
- revision `jhworks-staging-5342bd4f8acc`, traffic 100%, migration head `f30c9a71b624`.
- API image digest `sha256:c319bd20a44982d36aa4c17568d6cec29a0fc56b59f53533c60f5572675f123f`.
- web image digest `sha256:0bfa71ffd2217b6428da48b2780a31810a31f1d347395c8f0a3812e93e72665f`.
- 배포 계정의 HTTP smoke: liveness/readiness 200, 앱 인증 없는 보호 API 401, web 200, 총 4/4.
- 후속 GCP 읽기 조회: service/project public binding 없음, invoker IAM check 유지,
  익명 외부 접근 403, AI=false, public_demo=false, revision min=0/max=2 확인.

새 IAM 권한·유료 자원·AI key·공개 접근은 추가하지 않았다. 기존 승인된 이미지 build/push,
Cloud Run migration/release와 Cloud Shell 복원 실험만 실행했다. 실제 청구 총액은 이번에 조회하지
않았고, 기존 자원의 사용량 과금이 0원이라고 주장하지 않는다.

## 데이터 보존과 복원

| 구분 | 배포 전 | 배포 후 |
| --- | --- | --- |
| backup ID | `20261022T104327Z-1b8d914b` | `20261022T105221Z-0db223a2` |
| head | `c84f2a19d6e0` | `f30c9a71b624` |
| dump bytes | 42193 | 50847 |
| SHA256 | `8d111e98fced8c75942067750218f2563b7eaef4188b02abfd9e394ab3cb7727` | `4335661c6105cb1f2d2a68a11b1ce0b542ebb467f35de5cf85308f3875c41fd2` |
| dump 단계 초 | 195.0 | 12.04 |
| restore/검증 초 | 8.04 | 9.59 |
| 결과 | passed | passed |

동일한 고정 pgvector image digest와 socket-only/network=none 임시 복원 컨테이너를 사용했다.
두 번 모두 columns/constraints/indexes/ownership ACL/schema ACL/default ACL/rows/sequences/head 비교와
임시 컨테이너 정리를 통과했다. 첫 dump 시간에는 새 Cloud Shell의 이미지 준비가 포함돼 있으므로
위 차이를 DB 성능 개선 수치로 사용하지 않는다. 실제 dump는 Cloud Shell의 전용 비공개 디렉터리에만
있고 저장소/CI artifact에는 넣지 않았다. 주기·장기 백업 완료의 증거는 아니다.

배포 전후 승인/결재선/직원/부서/자격증명/연차/Agent/규정/규정절/일정 등 기존 10개 테이블의 행 수와
fingerprint를 읽기 전용 repeatable-read 트랜잭션으로 비교했다. 직원은 새 nullable
`demo_workspace_id` 열을 제외한 **기존 열**의 값을 비교하고, 별도로 새 열이 모두 NULL임을 확인했다.
원시 전체 행 hash가 바뀐 것을 데이터 훼손이나 완전 동일로 잘못 해석하지 않는다.
alembic head는 의도한 변경이며 login_budget은 업무 보존 비교 대상에서 제외했다.
새 demo_workspaces/demo_start_budget/demo_feedback/demo_feedback_gate 4개 테이블은 모두 0행이다.

## 미검증과 다음 순서

- 피드백 보관 정리 수정은 이 배포 이후 별도 PR이며 이 image에 포함됐다고 표현하지 않는다.
- 실제 visitor 생성/업무/피드백 접수는 public flag가 꺼져 있어 아직 실행하지 않았다.
- `groupware.pikan.dev`의 Hosting은 기존 정적 준비 화면이며 실제 앱 rewrite는 아직 없다.
- 공개 전용 배포/합성 공용 규정·일정/보관 정리 주기와 실패 감지를 준비하고 검증해야 한다.
- 공개 IAM·새 실행 계정/Secret·과금 자원이 필요해지는 시점에는 구체적인 적용안을 먼저 확인받는다.
- 실제 공개 검증 후 별도 포트폴리오 저장소의 라이브 데모·의견 남기기 버튼을 연결한다.
