# 데모 전용 신원으로 비공개 전환 준비

## 문제와 선택

2026-10-23 전용 credential 초기 설정은 실제 성공했지만 기존 `jhworks-demo`와 maintenance는
여전히 private staging의 runtime 계정/Secret을 참조한다. 새 schema·계정·키를 만들어 놓기만
해서는 실행 중인 서비스의 경계가 바뀌지 않는다. 다음 단위는 새 schema migration 후 이 참조를
전환하고 실제 HTTP·DB·IAM 검증을 하는 것이다. 인터넷 공개는 별도 단계다.

현재 배포된 이미지 source는 `75d5e8a98fb2919e46958f7d580b0aa287ed3705`다. 이 source 이후
API/웹 업무 코드와 Alembic revision history 변경은 없다. 변경은 운영 도구/profile/SQL과
Alembic test용 제공 Connection 경계이며 기본 CLI migration 경로는 유지된다.
따라서 이번 설정 전환에는 기존 검증 이미지 digest를 재사용한다. 새 image build는 코드가 바뀔 때 한다.
새 manifest 도구의 커밋을 기존 이미지의 빌드 source라고 표시하지 않는다.

Cloud Run revision은 계정/Secret 참조까지 불변이다. 기존 `jhworks-demo-75d5e8a98fb2`를 같은
이름으로 바꾸면 충돌한다. isolated profile은 검증된 기본 manifest의 정렬된 compact JSON에
SHA256을 적용해 `service-imageSHA12-configSHA12` 이름을 만든다. 같은 입력은 같은 이름,
Secret 버전 등 설정이 달라지면 다른 이름이다. full image source와 full config hash는 revision
annotation에 남긴다. 기존 private release와 리허설 generator의 계약은 유지한다.
Cloud provider가 추가하는 metadata까지 같은 hash로 증명하는 방식은 아니다.

## 검토 가능한 산출물

프로젝트 `jhworks-staging-tykimdream`, 리전 `asia-northeast3`, 전용 Secret version은 모두 1이다.
`app.ops.demo_isolation`과 기존 example의 project placeholder를 바꿔 offline 생성했다.
파일은 비밀 값 없이 `artifacts/cloud-run/isolated-rollout/`에 있으며 Git에는 넣지 않는다.

| 파일 | SHA256 |
| --- | --- |
| service.json | 49b6c6d9114d8243aec5252f3e985652ade19e4d51bc241cfef4190a2bb6534d |
| migration.json | 289cd7c01765ed99e63385448dd01022be6d3d364b8cd84373fd07b91f349fb0 |
| maintenance-dry-run.json | 163fccd1aae4079bcaa9c6bb9c04509b52bfde5ccbf2319a4afdf60f42011c28 |

대상 revision: `jhworks-demo-75d5e8a98fb2-3c51785fafdb`.

기존 검증 이미지:

```text
asia-northeast3-docker.pkg.dev/jhworks-staging-tykimdream/jhworks/api@sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0
asia-northeast3-docker.pkg.dev/jhworks-staging-tykimdream/jhworks/web@sha256:307dd6e9c9a59225adc465c0b17bc8e7bfeffea0b1ab867636dabd9252bedf12
```

manifest에 담긴 범위:

- 새 `jhworks-demo-migrate`: 전용 migrate 계정·migration DB/session v1, Alembic upgrade head,
  task1/parallel1/retry0/CPU1/512MiB/timeout300초. seed/기존 schema 복사 없음.
- 기존 `jhworks-demo`: 전용 runtime 계정·runtime DB/session v1, web/API 각각 CPU1/512MiB,
  min0/max1/concurrency4/timeout55초. IAM invoker 검사 유지, AI off, host/cookie 유지.
- 기존 `jhworks-demo-maintenance`: 전용 runtime 계정·동일 전용 v1, CPU1/512MiB/timeout120초,
  retry0/task1, dry-run만. Scheduler·실제 purge 없음.

## 승인 후 실제 순서와 실패 처리

1. manifest hash, 현재 image/revision·traffic·Job 설정, v1 ENABLED·정확한 SA/Secret policy,
   서비스/project 익명 grant 없음과 private 데이터 fingerprint를 읽어 확인한다. 현재 상태가 계획과
   달라지면 덮지 않고 중단한다. 기존 service/maintenance JSON도 복구용으로 보관한다.
2. 새 migration Job을 적용·1회 실행하고 성공/head 확인 전 서비스나 maintenance를 바꾸지 않는다.
   실패하면 로그의 안전한 오류 종류/단계를 조사한다. retry0이며 자동 재실행·downgrade·schema 삭제 없음.
3. service manifest의 traffic을 기존 revision100%로 고정한 candidate manifest를 만들고 적용한다.
   위 service.json hash는 최종 목표 설정이며 candidate/rollback 파일은 별도 hash로 기록한다.
   candidate Ready와 전용 SA/Secret/digest·max1/AI off/IAM을 확인한 뒤 새 revision100%로 전환한다.
4. 실제 인증된 readiness/guest 업무·피드백/방문자 격리·로그아웃을 검증하고, 기존 private 데이터
   fingerprint·권한 거부를 다시 비교한다. 별도 키의 상호 token 거부는 실제 검증 도구를 준비해
   증거를 얻기 전에는 완료로 표시하지 않는다. unit test의 키 교체 결과와 혼동하지 않는다.
5. 이 검증 후 maintenance 설정을 전용 참조로 바꾸고 dry-run 1회를 확인한다.
   실제 삭제와 예약 작업은 이후 별도 승인 대상이다.

서비스 검증 실패 시 기존 `jhworks-demo-75d5e8a98fb2`에 traffic100%를 복구한다.
이것은 DB migration의 rollback이 아니다. 새 demo schema는 보존하고 조사한다.
maintenance 변경 후 문제가 있으면 보관한 이전 Job manifest로 되돌린다.
기존 private staging의 서비스·Job·역할·Secret은 변경하지 않는다.

이 문서는 실행 계획이다. 새 Job 생성·실행/전용 SA·Secret을 사용하는 서비스·maintenance 업데이트는
아직 수행하지 않았고, 추가 컴퓨팅 및 인증 사용 범위 확인 후 진행한다. Hosting rewrite/DNS/public IAM,
유료 DB/LLM, 실제 삭제·주기 실행·새 IAM 권한은 이 전환에 포함하지 않는다.

## 검증과 남은 과제

로컬 관련 75 tests passed(1.49초), Ruff app/tests/alembic, strict mypy156 files 통과.
revision 충돌 회귀는 기존 이름과 차이·결정성·원래 image source·동일 container 설정·traffic 일치,
같은 이미지에서 Secret 버전 변경 시 새 revision 생성을 검사한다. 실제 cloud 적용은 미검증이다.
이 manifest 전환만으로 합성 공용 규정/일정, 실제 HMAC 상호 거부, 정리 운영·최종 브라우저 QA가
완료되지 않는다. [roadmap](roadmap.md)의 공개 전 checkpoint를 계속 따른다.

학습: artifact의 source identity와 배포 설정 identity를 구분해야 원인 추적·rollback을 정확하게 한다.
같은 source SHA만 revision 이름으로 쓰면 Secret rotation·리소스 설정 변경 때도 충돌한다.
Cloud Run이 이름을 자동 생성하게 두는 대안은 간단하지만 이 수동 검토 단계에서는 재현 가능한
candidate 이름과 traffic 복구 대상을 명시하기 위해 설정 hash를 선택했다.
