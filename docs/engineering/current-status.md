# 실행 상태와 다음 작업 — 2026-10-22

## 2026-10-23 재개: 공개 전용 경계 준비

[분리 기반 실제 적용](demo-identity-foundation.md): 사용자 승인 후 NOLOGIN DB 역할2/schema와
GCP SA2/빈 Secret3/v1 조건부 읽기4/deploy actAs2를 적용·독립 검증했다. 기존 행 수/head와
기존 Secret version1 유지, 새 버전0/관리 키0/project grant0을 확인했다. 서비스는 기존 75d5e8a 참조 그대로다.
다음은 [초기 credential 도구](demo-credential-setup.md)의 검증·리뷰·병합이며 실제 값 등록/LOGIN은
별도 비용·인증 승인 및 사용자 직접 입력 후 진행한다. 체크포인트 1은 아직 완료가 아니다.

첫 공개까지 5개 체크포인트와 이후 6개 단계를 [roadmap](roadmap.md)에 최신화했다.
[공개 데모 분리](demo-isolation.md)는 전용 schema/NOLOGIN DB 역할·GCP 계정/Secret 참조 profile과
실제 PostgreSQL 전체 migration/권한 회귀를 준비한다. 기존 staging과 실제 private demo 자원은
변경하지 않았다. 새 IAM/DB 권한·credential·Secret/Job 생성은 CI/리뷰와 적용 직전 확인 뒤 수행한다.

## 최신 실제 상태: 별도 데모 비공개 리허설 통과

[비공개 데모 리허설 증거](private-demo-rehearsal.md)가 현재 기준이다.
기존 staging은 release 39771645700 / revision jhworks-staging-75d5e8a98fb2 / smoke 4/4 성공.
PR #46은 exact-head CI 5개·자체 리뷰·라벨 후 병합했다(main 9ec7b34).
승인받은 jhworks-demo와 jhworks-demo-maintenance를 실제 생성했고, 익명403·max1·AI=false·v1 참조,
15개 HTTP 확인, 실제 Job dry-run 성공/삭제0을 확인했다. 전체 합성 생성량은 공간6/결재3/피드백3이다.
공유 runtime/session은 비공개 리허설용이다. 실제 공개·예약 실행·실제 삭제·Hosting rewrite는 적용하지 않았다.
다음은 공개 전용 신원/DB/key 경계와 정리 운영·실패 감지를 준비하고, 필요한 권한/비용/공개 전환을 확인하는 것이다.
domain은 여전히 준비 화면이며 포트폴리오 라이브 데모 버튼도 아직 연결하지 않았다.

아래 기록의 '아직 없음'과 이전 revision은 해당 작업 당시 상태다.

## 가장 최근 코드와 공개 준비
PR #42 방문자 lifecycle과 [PR #43 피드백](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/43)은
exact head CI 5개·자체 리뷰·reviewed/security 라벨 후 병합했다(main 5342bd4).
#43 CI API 382 passed/18 skipped, PostgreSQL 18 passed, 기본 browser 16 + 실제 public-demo 2 passed.
[방문자 lifecycle](demo-visitor-lifecycle.md)과 [피드백·개선 기록](demo-feedback.md)을 따른다.
공간 생성·정리 도구는 아직 실제 실행하지 않았다. public_demo_enabled 기본 false.

2026-10-22 후속 배포: main 5342bd4의 push CI 39764503071 성공 뒤 private release 39765860506과
smoke 4/4 성공. 실제 revision jhworks-staging-5342bd4f8acc/100%, DB head f30c9a71b624다.
기존 합성 업무 10개 테이블 보존과 새 head의 백업/격리 restore까지 통과했다.
[배포·보존·복원 증거](demo-private-release.md)를 따른다. AI=false/public_demo=false/익명403 유지.
domain은 정적 준비 화면이다.
이번 보강은 [보관 정리 실행 계약](feedback-retention.md)이며 자동 주기 작업이 운영된다는 뜻은 아니다.
PR #44는 최종 head ee35a63의 CI 5개 성공/자체 리뷰/라벨 후 병합했다(main a1d284e).
이후 [정리 Job runner와 적용 경계](demo-maintenance-job.md)를 구현한다. 기본 dry-run이며
새 외부 Job/Scheduler/IAM/자동 삭제는 승인 전 생성·활성화하지 않는다.
PR #45는 최종 head 77f93de CI 5개/리뷰/라벨 후 병합했다(main 75d5e8a).
CI API402/21 skipped, PostgreSQL21, browser16+2 통과. 실제 Job은 아직 없다.
다음 [공개 모드의 별도 비공개 리허설 서비스](public-demo-service.md)는 기존 staging을 덮지 않고
domain/cookie/resource 경계를 고정한 offline manifest를 준비한다. 새 자원 생성은 비용·권한 확인 후 수행한다.
웹 포트폴리오의 실제 버튼은 공개 폼이 검증된 뒤 연결한다. 실제 사용자 의견/만족도는 아직 없다.
공개 전용 DB의 합성 공용 규정·일정, 30일 정리 실행 경로, 최종 workspace E2E, Hosting rewrite/쿠키/
공개 IAM과 release 경로 검토가 남았다. 새 권한/실제 공개 수집·삭제·과금 자원 적용 전 확인받는다.

아래는 이전 실행 기록이다.

## 최신 코드 검증: token 만료 계약 완료, 방문자 workspace 기반 진행
[PR #40](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/40)을 정확한 head CI 5개 성공,
자체 리뷰 COMMENT·reviewed/security 라벨 후 병합했다(main f378e6b). 로컬/원격 작업 브랜치를 정리했다.
서명 token 필수 claim/시간 검증과 신규 69개 회귀를 추가했다. CI API 342 passed/10 skipped (28.06초),
별도 PostgreSQL 10 passed (3.74초), browser/container/dependency 성공.
[상세](session-expiry-contract.md)를 따른다. 실제 외부 staging은 아직 9a29f2e이고 이 코드를 재배포하지 않았다.

다음 단위는 [workspace 경계·수명·쓰기 예산](demo-workspace-boundary.md)이다. 새 공개 bootstrap·쿠키
전환·IAM 변경·실제 guest 계정은 아직 없다. workspace 생성 전체 상한/읽기·AI 제한/정리 정책/
공개 전용 인증 모드/화면과 Hosting 연결은 별도 작업이다. 전역 회사 일정·규정은 향후 공개용 합성
read-only 자료로만 구성해야 한다. private 데이터를 그대로 공개하지 않는다.

## 최신 상태: 사용자 도메인 HTTPS와 공유 로그인 예산의 비공개 배포 검증 완료

최신 배포는 [공유 로그인 예산·실제 배포 증거](public-demo-login-budget.md)가 기준이다. 실제 결재·휴가 업무의 마지막 검증은 [기존 workflow 증거](private-workflow-smoke.md)를 따르며 이번 배포에서 다시 실행했다고 표현하지 않는다.

- 최신 앱 SHA 9a29f2e0c0292ec9239600f896c0f68c1fb10daf, revision jhworks-staging-9a29f2e0c029, DB head c84f2a19d6e0. main CI·release 39728919669·smoke 4/4와 추가 HTTP/DB 검증 성공.
- 로그인 고정 분당 기본 60건을 DB 원자 카운터로 공유한다. 429·동시성·실패 지속성·DB 장애는 CI, 실제 카운터 쓰기·기존 업무 fingerprint 보존은 private staging에서 확인했다.
- PR #37/#38 리뷰·CI 5개·병합·브랜치 정리 완료. public domain은 정적 준비 화면이며 방문자 격리/쓰기 제한/공개 전환은 다음 단위다.

아래 npm 배포 SHA와 기존 backup은 과거 검증 이력이며 최신 앱 버전이 아니다.

- PR #28~32 병합 완료. #31/#32 최종 head CI 5개·직접 리뷰·라벨링 후 브랜치를 정리했다.
- 실제 staging은 `049f5d9ffc8bfdd56893749c091bd33b4878233f`, revision `jhworks-staging-049f5d9ffc8b`. main CI와 release 39721684081/HTTP 4/4가 통과했다.
- credential 3개를 포함한 새 backup/격리 restore 성공 후 private release와 HTTP smoke 4/4 성공.
- Cloud Shell read-only preflight 통과: 비공개 IAM, AI=false, max=2, 익명 403 유지.
- 실제 업무 workflow passed: 합성 결재 2건·연차 1일, 3명 권한/CSRF/409/logout 검증 완료. 초기 --apply 재실행 금지.
- 업무 데이터 포함 backup `20261022T040623Z-5fdce560`의 격리 restore/비교도 통과했다. [실제 업무 증거](private-workflow-smoke.md)를 따른다.
- npm 수정 가능 advisory는 [major별 전이 패치](npm-security-patches.md)로 처리했다. 동일 audit 8→1, web lint/type/build 통과. 잔여 braces는 별도 추적한다.
- 다음은 공개 demo의 사용자별 격리·초기화·요청/AI 비용 제한 설계와 회귀 검증이다. 공개 전환 전 확인은 유지한다.
- 현재 CD는 workflow_dispatch다. 공개 전환·새 권한/유료 자원·AI 연결은 별도 확인 대상이다.

도메인 최신 결과: [https://groupware.pikan.dev/](https://groupware.pikan.dev/)의 정적 준비 화면이 정상 TLS/hostname 검증과 HTTP 200을 통과했다. Firebase Hosting/Blaze와 groupware CNAME은 사용자 승인 후 적용했다. HTML/CSS hash, no-store/CSP, API·.env 404 및 루트 포트폴리오 HTTP 200을 확인했다. [실제 증거](pikan-domain-release.md)를 따른다. 앱·DB는 여전히 비공개이며 로그인 예산·방문자 격리 검증 후 실제 앱 연결을 진행한다. 아래의 승인 대기·인증서 검증 중 내용은 과거 이력이다.

이하 내용은 이전 실행 이력이다. 아래의 과거 배포 SHA·빈 DB backup·미배포 설명을 현재 상태로 해석하지 않는다.


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

1. 작성자/결재자/비참여자 private fixture 3명 생성은 이후 사용자 직접 입력으로 성공했다.
   도구가 department 1 / employee 3 / credential 3 / leave account 3을 출력했다.
   기존 backup은 생성 **전** 빈 업무 DB를 보관한다. 새 업무 데이터를 포함한다고 표현하지 않는다.
2. 로그인·일반 결재·휴가·비참여자 거부를 실제 command endpoint로 검증한다.
   [검증 도구와 판단](private-workflow-smoke.md)을 준비하며 실제 외부 업무 결과는 실행 후 기록한다.
3. 별도 작은 단위로 npm 패치/잔여 advisory, 공개 demo 격리·요청/비용 제한,
   backup 자동화와 main CI 성공 후 자동 배포를 연결한다. 이후 대표 화면 UI/성능 실험을 진행한다.

공개 demo/IAP/production·유료 AI 연결·새 유료 자원은 아직 완료하지 않았다.
Cloud Shell home의 작은 빈 DB 복원은 장기/예약 백업이나 업무 데이터 복구를 대체하지 않는다.
현재 CD는 workflow_dispatch로 시작하며 추가 Environment reviewer 승인만 제거한 상태다.
Cloud Shell의 사용자 실행용 source는 `~/jhworks-staging-tools/1b11879`에 full SHA를 대조해 준비했다.
앱 변경의 배포 SHA는 `1b11879`로 고정한다. 이후 상태 문서만 바뀐 main을 같은 이미지로 표현하지 않는다.

## 인증정보 교체 후 추가 상태

검증 계정 3개 교체 성공은 사용자 전달 결과로 확인했다. 이후 업무 검증은 initial_author_assigned에서
실패했으며 결재·휴가 생성 전이다. [교체 도구·실제 증거와 한계](../operations/private-staging-password.md)를
참조한다. 교체 명령을 다시 실행하지 않는다. 서버 목록 조회의 PostgreSQL 검증을 다음 단위로 진행한다.

## 배정 목록 PostgreSQL 재현과 수정

PR #28은 CI 4개·직접 리뷰·라벨링 후 병합했다. 별도 PR #29에서 동일 기존 쿼리의
실제 PostgreSQL 17.11 오류를 4 failed/3 passed로 재현했고 EXISTS 최소 수정을 준비했다.
[원인·대안·실험 경계](postgres-assigned-approvals.md)에 baseline job과 로컬 결과를 기록했다.
최신 head의 postgres 포함 CI 5개는 PR checks를 확인한다. live staging 배포/업무 재검증은 아직이다.
앱 배포 SHA는 여전히 1b11879다. credentials가 생긴 뒤의 새 backup/격리 restore를 확보한 후
현재 main CI→비공개 release→실제 업무 검증 순서로 진행한다. 기존 빈 DB backup을 현재 계정의
백업이라고 표현하거나 비밀번호 교체 명령을 다시 실행하지 않는다.

이번 실행 장애는 일반 pipe/기본 실행에서는 재현됐지만 Windows PowerShell의 PTY와 승인된
실행 경로에서는 명령이 정상 완료됐다. 후속 세션에서 같은 장애가 나면 이 차이를 먼저 확인한다.
플랫폼 승인·파일 권한 규칙을 우회한다는 뜻이 아니며 모든 확대 실행은 도구의 승인 검사를 따른다.

Domain continuation: PR #34 cache boundary merged at 569ad5f; hosting preflight branch prepares only a static page and offline validator. Firebase addition/Blaze/site creation and subdomain DNS are awaiting explicit approval; private Cloud Run is unchanged. See pikan-domain-release.md.

2026-10-22 live domain milestone: explicit Firebase/Blaze and CNAME approvals received. Static Holding release 1792645703936000 is live on jhworks-staging-tykimdream.web.app; groupware CNAME is authoritative/public. Firebase ownership and host are active; certificate is validating (05:10 UTC), so custom HTTPS is not yet complete. Root portfolio HTTP 200 and private Cloud Run HTTP 403 were verified. Interactive demo remains gated.
