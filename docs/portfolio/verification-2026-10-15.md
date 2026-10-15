# 2026-10-15 개선 검증 기록

## 최초 분석

- 실제 저장소: `/Users/jihwan_kim/Project/groupware RAG`, remote `tykimdream/JHWorks-AI-Groupware`.
- 시작 HEAD: `9ad0bcd`. 최초 구현 2026-08-21, 마지막 기존 커밋 2026-08-30. 시작 시 working tree clean.
- 로컬 README는 Phase 11, 공개 GitHub에서 확인한 README는 Phase 7이었다. 로컬 구현을 기준으로 작업했다.
- 기존 구현: 자연어 휴가 상담, deterministic availability, 정책 검색, signed preview, 멱등 DRAFT,
  별도 제출 확인과 durable workflow가 이미 있었다. 새 Agent나 도메인 서비스를 추가할 필요가 없었다.
- baseline `pnpm validate`: API 108 tests 및 lint/type/build 통과.
- 발견: 9월 고정 검색 기본값, 요청 중 오래된 후보, 상담 완료 뒤 지원하지 않는 후속 답변 UI,
  요청의 상대 날짜를 모델 출력과 대조하지 않는 경계, 이전 사용자 상태 초기화 부족,
  실제 UI 스크린샷과 사람의 효과 측정 절차 부재.

## 변경과 검증 범위

- 날짜 기본값은 Seoul 오늘부터 30일, 같은 연도 안에서 구성한다. 2026년 9월 seed와 테스트 날짜는 유지한다.
- ‘다음 주/next week’는 다음 월요일~일요일로 대조한다. 기간을 바꾸는 실제 날짜 답변은 우선하며,
  일수만 답한 경우 기존 상대 기간 검증을 유지한다. 일반 자연어 파서를 새로 만든 것은 아니다.
- 프론트엔드는 요청 중 결과를 비우고 조건 변경 시 결과를 무효화하며, 동기식 ref guard로 중복 클릭을 막는다.
- component unmount는 읽기와 쓰기 HTTP 요청의 client 대기를 취소한다. 서버 쓰기의 취소를 보장하는 것은 아니며,
  확인 token과 멱등 저장이 데이터 정합성을 책임진다.
- 탭 focus 시 계정을 재확인한다. 확인 중 이전 업무 화면을 숨기고, 직원이 바뀌면 key로 상담 상태를 새로 만든다.
- 기존 `/attendance/overview`를 수동 탐색에 연결해 가용/사용/대기 연차, 회사/부서 일정과 팀 휴가를 확인한다.
  팀 휴가의 사유는 API가 반환하지 않는다.
- 일반 업무 Assistant의 읽기 Tool 4개 및 round/call 제한은 유지한다. 휴가 시나리오는 기존 전용 workflow를 재사용한다.
- 기존 GitHub CI를 유지하고 비용 없는 실제 API 브라우저 job을 추가한다.

## 결과

| 실행 명령 | 결과 |
| --- | --- |
| `pnpm validate` | API lint, mypy 99 files, 111 tests 및 web lint/type-check/build 통과 |
| `pnpm test:e2e` | desktop 4개 + mobile 4개 = 8개 통과 |
| `git diff --check` | 통과 |

브라우저 주요 경로는 키보드 Enter로 날짜 선택과 저장을 실행하고 확인 전 저장 없음과 단일 확인 HTTP 요청을 검사했다.
초기 browser fixture는 CORS 설정 순서와 in-memory SQLite 공유 연결 문제로 실패했다.
fixture 초기화 순서를 고치고 격리된 임시 파일 DB로 전환한 뒤 위의 최종 검증을 통과했다.
기존 저장/제출 멱등성과 권한 및 version 테스트는 기존 API suite에 포함되어 재실행했다.
Playwright는 격리된 임시 SQLite DB와 기존 seed, 가짜 LLM/임베딩 provider를 사용한다.
기존 개발 DB와 `.env`는 변경하지 않는다. HTTP/인증/권한/후보 계산/서명/저장은 실제 application 코드다.
provider 장애 시나리오만 browser route로 503을 주입한다.

## 스크린샷 출처

`docs/portfolio/screenshots/`는 Playwright가 실제 구현된 UI에서 촬영했다.
`leave-candidates-*`: 날짜 후보, `leave-preview-*`: 저장 전 실제 초안 영역,
`leave-draft-*`: 저장된 문서 화면. desktop/mobile은 Chromium에서 실행하며 mobile은 viewport emulation이다.
실제 휴대폰 검증이나 실제 OpenAI 출력 화면으로 주장하지 않는다.

## 미검증

이번 작업에서 실제 모델 평가, PostgreSQL 동시 실행, container 재배포와 외부 demo 배포는 실행하지 않았다.
기존 로컬 eval artifact는 역사적 기록이며 이번 결과와 구분한다.
사람의 효과 측정은 `task-study.md`와 빈 CSV에 따라 진행 대기 중이다.
공개 운영에는 release runbook 외에도 SSO, CSRF, 계정 관리와 운영 audit 검토가 필요하다.

## PR 반영 및 배포 전 패치

기존 release 통합 PR #16에 이번 변경을 반영한다. main보다 앞선 자연어 상담, confirmed Draft,
durable submit 및 운영 준비 커밋을 포함하며 기존 이력을 보존한 merge commit으로 통합한다.
배포 전 점검에서 Next.js/eslint-config-next를 16.3.8, PyJWT를 2.15.1로 패치하고
source-map-js는 기존 ^1.2.1과 호환되는 1.2.2로 override했다.
`pnpm audit --prod`의 알려진 취약점은 0건이며 개발 도구 전체 감사 결과와는 구분한다.
패치 후 API 111 tests, 전체 validate와 desktop/mobile browser 8개를 다시 통과했다.
공개 호스팅 대상은 별도 확인이 필요하다. 로컬 배포 검증은 기존 DB와 분리된 PostgreSQL 볼륨으로 수행한다.
