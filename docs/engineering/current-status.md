# 실행 상태와 다음 작업 — 2026-10-22

## 구현·리뷰·CI·병합 완료

사용자는 PR 생성·코드 리뷰·라벨링·문제 없는 변경의 병합을 위임했다. 아래 PR에는 직접 코드 리뷰의
범위와 한계를 COMMENT로 기록하고 reviewed/분류 라벨을 붙였다. 독립적인 사람의 승인으로 표현하지 않는다.
모두 validate/browser/container-smoke/dependency-review 4개 성공 후 병합했다.

| PR | 구현과 증거 |
| --- | --- |
| [#21](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/21) | 작은 staging dump/격리 restore, Action ID token 전달, 안전한 배포 실패 작업명 |
| [#22](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/22) | QA-01 UTF-8 JSON/자식 프로세스 계약. 실제 Windows cp949 실패 재현·회귀 |
| [#23](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/23) | 공개 기본 비밀번호를 쓰는 로컬 seed의 원격 DB/환경 오사용을 연결 전 차단 |
| [#24](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/24) | certifi 2026.10.19·Mako 1.4.3, 두 전이 패키지 잠금/해시만 갱신 |
| [#25](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/25) | 비공개 staging 합성 fixture 준비 도구. 기본 read-only, 실제 생성은 별도 사용자 입력 |

최종 애플리케이션 main `1b118797e32fdfad987a5c8f118f8ec0cb5312f8`.
로컬 cp949 기본 모드 API **230 passed / 18.03초**, Ruff app/tests/alembic,
strict mypy app/tests 112 source files 통과. 해당
[main CI 39708092246](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39708092246)도 성공했다.
이번에 만든 #21~25의 정확한 병합 head만 확인해 원격·로컬 작업 브랜치를 정리했다.

## 실제 외부 검증

- 첫 일반 private release `2dfb0d0`는 CI deploy-SA ID token의 HTTP 4/4까지 성공했다.
  후속 GCP 조회에서 Ready/traffic 100%, service/project public binding 없음,
  invoker IAM check 활성, AI=false, service max=2, 익명 GET 403을 확인했다.
- 보안 패치 포함 `1b11879`의
  [최종 release 39708645497](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39708645497)도 성공했다.
  2026-10-22 11:00:00 KST에 deploy-SA HTTP 4/4를 통과했고,
  `jhworks-staging-1b118797e32f` revision의 private/traffic 100%/AI/max 경계와 익명 403을
  실제 source의 read-only preflight로 다시 확인했다. 이때도 계정은 생성하지 않았다.
  API digest `sha256:3369c427a678a0c47cbc1e0c65195f771fabaf436634bc73b3665c4a2ddba564`,
  web digest `sha256:ab284ed22cd0888d114758f4f9f245a0817f10e90019e0af266767a084b0bf3f`.
- 고정된 fixture source `0490b26`를 Cloud Shell의 별도 checkout과 frozen dependencies로 실행했다.
  실제 archive hash·private service·migration head·빈 Supabase 업무 DB의 read-only preflight를 통과했다.
  **이 시점 계정은 생성하지 않았다.**
- 새 backup ID `20261022T015155Z-b817c140`, 39,501 bytes,
  SHA256 `3e802b710d80dcaca5b1d72d0079da6a219805abe42bf663b2ea7ef674937670`.
  head `b63d91e52fa0`와 11 tables의 schema/data/ACL/sequence 비교 성공, 업무 10 tables는 0행.
  원본 복원/삭제 없음, temporaryContainerRemoved=true.
- dump 단계 267.13초, restore/비교 9.10초. 새 Cloud Shell에서 image가 없고 Docker 단계가 진행되는
  것을 별도 읽기 전용 terminal로 관찰했다. dump 시간은 image 준비를 포함한 전체 명령 시간이며
  DB query 성능이나 대용량 RTO 수치로 비교하지 않는다.
- 패치 병합 뒤 GitHub Python open alerts는 0개로 조회됐다. npm open alerts 8개는 남아 있다.
  `pnpm why`에서 brace-expansion/braces/js-yaml은 eslint-config-next·ESLint 개발 의존성 경로였다.
  이를 모든 runtime copy가 안전하다는 증거로 해석하거나 alert를 dismissed 처리하지 않는다.

## 지금 이어갈 순서

1. 사용자가 직접 인증정보를 설정해야 하는 단계에서만 확인한다. 작성자/결재자/비참여자 3명의
   private fixture는 [운영 절차](../operations/private-staging-fixture.md)에 따라 만든다.
   기본 demo1234·실제 사람 정보·GCP/Supabase 비밀번호 재사용은 금지한다.
2. 로그인·일반 결재·휴가·비참여자 거부를 실제 command endpoint로 검증한다.
3. 별도 작은 단위로 npm 패치/잔여 advisory, 공개 demo 격리·요청/비용 제한,
   backup 자동화와 main CI 성공 후 자동 배포를 연결한다. 이후 대표 화면 UI/성능 실험을 진행한다.

공개 demo/IAP/production·유료 AI 연결·새 유료 자원·실제 fixture 생성은 아직 완료하지 않았다.
Cloud Shell home의 작은 빈 DB 복원은 장기/예약 백업이나 업무 데이터 복구를 대체하지 않는다.
현재 CD는 workflow_dispatch로 시작하며 추가 Environment reviewer 승인만 제거한 상태다.
Cloud Shell의 사용자 실행용 source는 `~/jhworks-staging-tools/1b11879`에 full SHA를 대조해 준비했다.
앱 변경의 배포 SHA는 `1b11879`로 고정한다. 이후 상태 문서만 바뀐 main을 같은 이미지로 표현하지 않는다.
