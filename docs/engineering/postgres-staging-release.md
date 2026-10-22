# PostgreSQL 수정의 비공개 staging 배포 — 2026-10-22

## 문제와 코드 검증

배정 결재 목록의 JOIN + DISTINCT가 PostgreSQL JSON equality 부재로 실패했다.
[PR #29](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/29)의 EXISTS 수정은
JSON 응답과 결재 이력을 유지하면서 목록 중복을 방지한다. 새 라이브러리나 migration은 없다.
[재현 및 대안 비교](postgres-assigned-approvals.md)를 함께 읽는다.

- PR head `d4bc840b401affc2e80a53cf1f208e1fc6e5015b`의 CI 5개 성공 후 직접 리뷰 COMMENT와 reviewed 라벨을 확인해 병합했다. 독립된 사람의 승인으로 표현하지 않는다.
- 병합 SHA `cfe258ff24f151fbb412b4a53b74788d9c48dd96`.
- #28/#29의 병합된 원격·로컬 작업 브랜치를 정리하고 로컬 main을 fast-forward했다.

## 배포 전 실제 백업·복원

기존 승인된 Cloud Shell, Supabase staging, 임시 로컬 Docker 컨테이너에서 수행했다.
새 클라우드 자원이나 권한은 만들지 않았다. 원본 DB 복원·데이터 삭제는 수행하지 않았다.

- backup ID: `20261022T033845Z-2535fdd7`
- archive: Cloud Shell home의 `jhworks-staging-backups/20261022T033845Z-2535fdd7/groupware.dump`
- 40,091 bytes; SHA256 `55ca01ae3b0229bd3b5123616216bc379de56745bb8666d5d269929ec56d877e`
- backup reference: `cloud-shell:20261022T033845Z-2535fdd7:sha256:55ca01ae3b0229bd3b5123616216bc379de56745bb8666d5d269929ec56d877e:restore-verified`
- dump 단계 12.19초, 격리 restore/비교 9.62초. DB 성능 개선율이나 대용량 RTO로 해석하지 않는다.
- migration head `b63d91e52fa0`; columns/constraints/indexes/ownership/schema/default ACL/rows/sequences/head 비교 성공.
- 합성 직원·credential·leave account 각 3행, 부서 1행. approvals/approval lines/calendar 0행.
- `status=passed`, `temporaryContainerRemoved=true`. dump·비밀 값은 Git에 포함하지 않는다.

이 백업은 비밀번호 교체 후 fixture를 포함한다. 결재·휴가 업무 검증 전 checkpoint이며 장기·예약 백업이 아니다.
교체 성공과 업무 검증 성공을 구분한다. 비밀번호 교체 명령을 다시 실행하지 않는다.

## 배포와 업무 검증

- [main CI 39719068422](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39719068422): success. validate/postgres/browser/container-smoke 성공; dependency-review는 push 조건으로 skipped(PR에서는 성공).
- [private release 39719348765](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39719348765): success, 총 2분 37초. bootstrap=false, 위 backup reference 사용.
- revision `jhworks-staging-cfe258ff24f1`. migration, private release, deploy-SA HTTP smoke 4/4 통과.
- 2026-10-22 12:56 KST 이후 동일 SHA의 Cloud Shell read-only `service-preflight`도 passed, changed=0.
  이 검사는 Ready/traffic 100%, public binding 없음, invoker check 활성, AI=false, service max=2를 확인한다. 익명 HTTP 403은 별도 curl로 확인한다.
- release record의 app session 없는 API 요청은 401, liveness/readiness/web root는 200이다. GCP 인증을 쓰는 smoke와 익명 ingress 403은 별도 경계다.

API digest: `sha256:9a9f871e5cf24db1b81b97f7aa15e20939c34c30ef8f9d2cfc80846a78ad4a28`

Web digest: `sha256:f982bb3ae7aeb11891c2e8473353582f716077737c4bfdf259e85ad20c45bddd`

실제 업무 검증은 기존 fixture 비밀번호의 숨김 입력 단계에서 대기한다. 명령은 별도 고정 SHA worktree에서 실행한다.
일반 확인 문구 입력이나 비밀번호 재설정은 없다. 기존 새 fixture 비밀번호를 입력한 뒤에만 합성 결재 2건·연차 1일 검증이 진행된다.
아직 로그인/결재/휴가 workflow 성공으로 기록하지 않는다. 실패하면 자동 재실행하지 않고 stage와 업무 생성 여부부터 확인한다.

## 다음 단계와 한계

1. 기존 비밀번호 직접 입력 후 실제 workflow 결과를 별도 증거로 기록한다.
2. npm advisory 잔여 항목과 공개 demo의 사용자별 격리·초기화·요청/AI 비용 상한을 작은 PR로 검증한다.
3. 백업 보관 위치·복구 가능성을 먼저 정한 뒤 CI 성공 후 CD 자동 실행을 연결한다. 현재는 workflow_dispatch이며 staging 추가 reviewer 승인만 제거돼 있다.

공개 접근·유료 AI·UI 수동 검증·대용량 실험은 이 배포 결과의 범위가 아니다.
Cloud Shell 임시 로컬 컨테이너의 복원 성공은 장기 백업, 장애 시 복구, 실제 기업 운영 증거를 대체하지 않는다.
Docker GitHub Actions의 Node 20→24 강제 전환 경고와 ubuntu-latest 26 전환 공지가 남아 있으며, 별도 CI 유지보수 항목으로 추적한다.
