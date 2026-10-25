# 현재 상태와 작업 기록 — 2026-10-25


## 앞으로의 실행 기준 — 2026-10-25

[현재 로드맵](roadmap.md)과 [작업 ID별 실행 계획](execution-plan-2026-10-25.md)이 과거 기록의 다음 순서를 대체한다.
아래 일자별 항목은 구현·검증 이력이다. 계획 문서화는 새 제품 기능의 완료나 원격 적용을 뜻하지 않는다.

| 항목 | 기준 상태 |
| --- | --- |
| 마지막 제품 기준 | main `b9831c7` / PR #74, 사이드바 Tailwind4·공개 반영 확인 |
| 공개 대표 흐름 | 경비 작성·보완·제출·역할 전환·승인, API/문서/Pattern 제공 |
| 공개 AI / 자동 정리 | 마지막 배포 기록 OFF / OFF. 실제 변경 전 재대조 |
| 실제 AI / 사람 평가 | 고정 합성 2건 점검 / 신규 사용자 측정 대기 |
| Storybook / npm | 미설치·미배포 / private·미게시 |
| 다음 작업 | M0-01 대표 경비 계약 + M2-01 평가 대조·offline 회귀 확장 |
| 외부 조건 대기 중 | M1 증거 대조·M2 offline/예산·M3 로컬 개선 중 독립 작업 진행 |


## 2026-10-25 PC 사이드바·Tailwind 도입

사이드바 하단의 안내·역할 전환·프로필을 하나의 footer로 묶고 로그아웃을 계정 행 안에 배치했다.
PC에서는 메뉴만 스크롤하며 계정 동작은 화면 아래에 남긴다. 모바일은 일반 흐름과 가로 메뉴를 유지한다.
Tailwind 4·PostCSS를 도입해 이 영역부터 전환했으며, `tw:` prefix와 JHW 토큰 bridge를 사용한다.
Preflight는 제외하고 전환한 영역의 기존 CSS 선택자를 제거했다. 전체 CSS 전환은 완료되지 않았다.
[도구 역할과 Storybook 도입 기준](../design/styling.md)에 문서와 검증 환경의 차이를 기록했다.
Storybook은 아직 설치·배포하지 않았다.

## 2026-10-25 SaaS UX·첫 방문 가이드·JHW Pattern

[공식 디자인 시스템 비교](../design/ux-principles.md)를 바탕으로 공개 홈의 비활성 AI 입력창을
경비 작성 시작점과 다음 행동으로 바꿨다. 첫 사용자에게 작성·제출·승인 3단계 가이드를 제공하며,
닫기·다시 보기·키보드·스토리지 차단을 지원한다. 가이드는 비모달이고 자동 표시에서 포커스를 빼앗지 않는다.
주요 화면의 Draft 문구를 초안으로 정리하고 필수 안내와 보충 툴팁을 구분했다.

`packages/pattern`의 의미 토큰을 원본으로 CSS와 문서 목록을 생성하며, 제품과 공개 `/pattern`이
같은 Button·Badge를 사용한다. 기존 변수명은 별도 legacy.css로 연결한다. 패키지는 private이며
npm에 게시하지 않았다. 라이선스·이름·소유권과 공개 API는 외부 게시 전에 확정한다.
원격 배포 결과는 PR·release 기록과 구분하며 공개 AI·정리·비용 설정은 변경하지 않는다.

## 2026-10-25 API 문서·프로젝트 소개·PC 캡처 정리

Swagger를 전자결재·근태/휴가·정책·조직·업무 도우미·인증/체험·운영의 7개 업무 도메인으로 묶고,
40개 API에 한글 제목과 동작 설명을 붙였다. 경로·입력·응답·업무 로직은 변경하지 않았다.
인증·제약 설명은 API 가이드에 두고 Swagger 첫 화면에서는 대표 흐름과 도메인 탐색을 안내한다.

README는 제품 설명과 기술 선택을 다듬고, PC 화면을 1440×900 뷰포트에서 맨 위로 스크롤한 뒤
재촬영했다. 추가 화면은 접어서 볼 수 있게 했다. PC 사이드바의 grid 정렬을 명시하고, 프로필의
긴 부서명 줄바꿈과 공개 공간의 내부 식별자 표시를 정리했다. 업무 홈·경비 상세를 각각
1024/1280/1440/1920px에서 가로 넘침과 스크롤 시 사이드바 위치로 검증한다.

`.env.example`은 키가 빈 템플릿이며 로컬 DB 예시 비밀번호를 운영에서 쓰지 않도록 주석을 보강했다.
`.env.*` 실설정 파일을 Git에서 제외하고 예시 템플릿만 예외로 두었다. 실제 키 파일은 읽거나 변경하지 않았다.
이 소스 검증과 원격 배포 결과는 해당 PR 및 release 기록에서 구분한다.

## 2026-10-24 프로젝트 소개와 공개 결재 UX

README를 기업 경비 정산 문제·대표 체험·네 가지 역량·실제 공개 범위 중심으로 다시 구성하고,
로컬 계정·Docker·AI 설정은 [개발 가이드](../development.md)로 옮겼다. 과거 단계의 완료 목록을
현재 운영 상태로 오해하지 않도록 최신 소개와 검증 기록을 분리했다.

수동 결재 명령의 브라우저 confirm을 앱 내부 확인 창으로 바꿨다. 문서·금액·버전·의견을 보여 주며,
취소에 초기 포커스를 두고 Tab 순환·Esc 취소·닫은 뒤 포커스 복원을 제공한다. 확인 전에는 쓰지 않고,
처리 중 중복 실행을 차단한다. 서버의 권한·version 검증은 기존 명령을 그대로 사용한다.
공개 모드 브라우저 회귀는 API로 작성·제출·승인하던 경로를 실제 폼·버튼·역할 전환으로 변경했다.
데스크톱/모바일에서 취소·Esc의 무변경과 제출 한 번, 승인 상태·의견을 확인했다.
이 기록의 로컬 검증과 원격 배포 결과는 해당 PR 및 release 기록에서 구분한다.
공개 AI·자동 정리·비용 설정은 이 변경으로 활성화하지 않는다.

## 2026-10-24 공개 체크포인트와 문서화

공개 demo 서비스·Hosting rewrite와 포트폴리오 라이브 링크를 적용했다. 기존 환경의 실제 도메인 HTTP21개가
통과했고, 브라우저는 경비 초안 저장까지 확인했다. 제출 confirm 창에서 브라우저 제어가 중단됐으므로
HTTP 승인 성공을 브라우저 전체 E2E 성공으로 주장하지 않는다. 포트폴리오 PR37 병합·운영 배포·한영 링크를 확인했다.

프로젝트 Cloud Run 월5천원 spend cap은 CONFIGURED, 프로젝트 전체 월1만원 알림은 actual50/80/100%와
forecast100%다. 한도는 무료 크레딧 전 추정 비용이며 staging도 포함한다. 지연 초과분과 타 서비스 비용이 있어
월 총액 절대 상한은 아니다. 공개 AI와 자동 정리는 계속 OFF다. 보관30공간에 닿으면 신규 체험은 중단된다.

이번 변경은 Swagger 경로·인증·업무 설명·경비 요청 예시와
[API 안내](../api/README.md), [GitHub 아키텍처 그림](../architecture/README.md), README 현행화를 준비한다.
공개 AI 검토 버튼과 홈 안내를 현재 제공 범위에 맞춘다. 이 소스 변경의 배포 검증은 병합·release와 구분한다.
다음은 공개 모드 화면/모바일 마감 → 승인된 정리 적용 → 별도 OpenAI 예산·평가 후 경비 AI 공개다.
아래 항목의 미공개·미배포 표기는 각각의 과거 시점 기록이다.

## 2026-10-24 제품 기능: 경비 사전 점검과 근거 문서

홈과 경비 상세에 필수 지출 정보 보완·중복 가능성을 먼저 제안한다.
같은 작성자/지출일/사용처/금액을 비교하고 자기 자신·반려 문서를 제외한다. 결재자에게는 열람 가능한
근거만 반환하며 방문 공간 경계도 적용한다. 홈 최근10문서·문서당 근거3개로 범위를 표시한다.
규칙 기반 읽기 전용 점검이며 LLM 판단·자동 제출·자동 반려가 아니다.
API507 passed/PG29 skipped, 기존 브라우저28개 통과와 새 제안4개 수정 후 통과, 공개 체험2개 통과.
[구현 범위·증거·제약](expense-insights-2026-10-24.md)을 따른다. 로컬 합성 예시로 화면을 바로 체험할 수 있다.

## 2026-10-24 제품 기능: CES 경비 정산

출장 신청과 구분되는 EXPENSE 상세 구조와 실제 지출 검증을 연결했다.
자연어 경비 요청→누락 정보 질문→경비 규정 미리보기→명시적 초안 저장→수정→제출→관리자 승인까지
데스크톱/모바일 화면 회귀가 통과했다. 서버의 지출 검증은 초안 준비·제출·검토에서 공유한다.
기존 DB의 EXPENSE enum과 JSON details를 활용하므로 DB migration과 원격 배포는 수행하지 않았다.
API499 passed/PG29 skipped, 기존 브라우저25 passed와 수정 후 경비 브라우저2 passed,
공개 체험2 passed를 확인했다. 최종 경비 화면 수정 후 관련2개도 재검증했다.
영수증 참조는 원본 첨부로 취급하지 않으며 실제 업로드·원본 검증·실제 AI 품질은 완료하지 않았다.
[구현 범위와 남은 일](expense-settlement-2026-10-24.md)을 따른다. 아래 ‘경비 미지원’은 이전 단계 기록이다.

## 2026-10-23 제품 화면: 업무 홈·AI 초안 스튜디오

사용자가 제시한 풀스택·프론트엔드 패턴/토큰·UI/UX·기업 AI 업무 지원을 제품 목표로 삼는다.
출장·경비 중심 업무 공간을 대표 경험으로 발전시키며, 휴가는 보조 사례로 활용한다.
업무 홈과 공통 탐색, 디자인 토큰, AI 요청 전달·추가 질문·규정 미리보기·확인 후 저장 화면을 구현했다.
홈의 현황·최근 문서·다음 할 일은 현재 계정의 실제 API 결과로 계산한다. 다음 할 일은 문서 상태 기반 제안이며
새 proactive AI Agent를 구현한 것은 아니다. 결재 목록의 이전 응답 덮어쓰기와 활성 탭 재클릭 문제도 수정했다.
일반 E2E24개·공개 체험 E2E2개가 통과했고 최종 목록 수정의 데스크톱/모바일 재검증2개가 통과했다.
[화면 범위·한계·재현](workspace-ui-2026-10-23.md)을 따른다. 로컬 AI는 명시된 scripted fixture이며,
실제 모델 품질·지출 후 경비 정산·실제 선제 제안·공개 도메인 배포는 완료하지 않았다.

## 2026-10-23 사용자 피드백 반영: 제품 작업 우선

최신 순서는 [작업 우선순위](priorities-2026-10-23.md)를 따른다.
다음은 결재 목록 응답 경합 수정과 실제 화면에서 작성·제출·승인/반려·휴가 흐름을 완결하는 작업이다.
AI 휴가 상담·초안 대표 흐름, 대표 화면 사용성, 방문자 체험을 이어서 처리한다.
정리/알림의 추가 원격 실행과 장시간 관찰은 공개 준비 때로 미룬다. Scheduler는 마지막 확인 시 PAUSED였으며,
미확인 복구 실행 결과는 완료로 간주하지 않는다. 아래 A3 준비 기록은 당시 상태로, 지금의 다음 작업이 아니다.

## 2026-10-23 A3: 정리 예약·실패/누락 감지 적용 준비

새 retention Job의 dry-run/apply, OAuth Scheduler, Job 범위 invoker와 disabled 실패/성공 누락
정책을 생성하는 offline 도구·회귀13개를 준비했다. 전체 API490 passed/PG29 skipped(로컬), Ruff/mypy 통과.
기존 Job의 전용 신원·Secret v1·dry-run/batch5/고정 digest를 읽기 확인했고,
Scheduler API 비활성/알림 채널0/정책0, 실제 `succeeded` 지표와 PromQL 정상/누락 대조4개를 확인했다.
자원 생성·새 IAM·Job 실행·알림 발송·삭제는 하지 않았다. 사용자가 기존 계정 이메일 수신을 선택했으며
[변경·비용·단계·복구 절차](demo-retention-operations.md)를 검토해 첫 dry-run 기반 시설 적용을 확인해야 한다.
자동 정리 활성화/실제3시간 누락 incident·수신·첫 apply·자연 예약 완료 전에는 A3 완료가 아니다.

## 2026-10-23 20:50 KST: 실제 HTTP 세션 경계 검증 성공

PR #61 exact-head CI5개·자체 리뷰·reviewed/security 라벨 후 병합(main `2357ca4`).
앱 내부 Cloud Shell에서 고정 도구를1회 실행해 HTTP13개가 통과했다.
정상 세션은 교차 요청 전후4회200, 양방향 상대 세션은 서명 오류401 각1회,
logout2회200/무쿠키2회401이다. private session Secret v1/기존 ID token 각1회 사용,
합성 방문 공간1개 생성·정상 조회 예산2회 소비, 업무 결재/피드백0이다.
키/JWT/cookie 원문을 출력·저장하지 않았다. 서비스 배포·새 IAM·공개 전환·정리 실행은 없다.
[실제 결과와 한계](demo-http-session-boundary.md)를 따른다. 실행 계획 A2의 HTTP 조건을 충족했다.
다음은 A3 정리 주기·실패/실행 누락 감지다. Cloud Scheduler API 비활성 상태였으므로
구체적인 설정·신원·비용·알림 수신 경로를 준비하고 적용 범위를 확인해야 한다.
아래 '서비스 간 HTTP 세션 검증 남음'은 당시 기록이다.

## 2026-10-23 19:37 KST: 실제 세션키 분리 검증 성공

PR #58/#59는 각각 exact-head CI5개·자체 리뷰·라벨 후 병합했다.
사용자의 다음 단계 진행 요청으로 기존 private/demo session Secret v1을 각1회 메모리에서 읽었다.
고정 source/hash 확인과 중복 방지 attempt 후 실제 키 검증 exit0:
서비스 참조2/서로 다른 키2/자체 서명 수락2/상대 서명 거부2, HTTP0/write0이다.
키·JWT 원문을 출력/저장하지 않았고 Secret 재접근 없이 결과 파일·hash·0600/0700을 확인했다.
[실제 증거와 한계](demo-session-key-boundary.md)를 따른다. 서비스 배포·데이터 변경·Job 실행은 없었다.
서비스 간 HTTP 세션 검증, 정리 주기·실패/실행 누락 감지와 최종 공개 QA는 남아 있다.
아래 '원격 세션키 검증 전'은 당시 기록이다.

## 2026-10-23 후속: 정리 실행 증거 대조와 사전 점검 보강

앱 내부 브라우저에서 기존 Cloud Shell 인증을 연결하고, 저장소에 없던 오전 정리 결과를 발견했다.
실제 execution3건의 완료 시각/succeeded1/failed0과 Cloud Logging 앱 보고서1개씩을 읽어 대조했다.
dry-run planned1/removed0 → apply planned1/removed1 → 재실행 planned0/removed0이며
feedback은 모두 expired0/removed0/stored1이다. 이번에 삭제/Job 실행을 새로 한 것이 아니다.
현재 Job은 전용 runtime/DB·session v1/기본 dry-run을 유지한다.
[세부 증거와 한계](demo-retention-rehearsal.md)를 따른다. 현재 DB 보존 재대조·주기 실행·실패/누락 감지는 남아 있다.
아래 '실제 정리 미실행'은 당시 저장소 기록이며, 같은 작업을 반복 실행하지 않는다.

사전 SQL에 실제 정리 순서의 첫 대상·건수·관찰/정리 가능 시각을 추가했다.
최신 빈 후보를 실제 삭제 대상으로 혼동하지 않도록 하고 PostgreSQL 회귀를 추가했다.
작업 PR은 [#58](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/58)이며 병합 여부는 PR 상태를 따른다.
다음은 원격 세션키 경계 검증과 정리 운영 준비다.

2026-10-23 저장소 분석에 따른 [실행 계획](execution-plan-2026-10-23.md)을 추가했다.
바로 다음 단위는 기존 정리 리허설 완결이며, 원격 키 경계·정리 운영·최종 QA·공개·포트폴리오 순서로 진행한다.
이 계획 추가로 실제 외부 자원·데이터·배포 상태가 바뀌지는 않았다.

## 2026-10-23 재개: 공개 전용 경계 준비

최신 실제 상태: [전용 신원 전환 검증](demo-isolated-rehearsal.md) 성공. demo revision은
`jhworks-demo-75d5e8a98fb2-3c51785fafdb`/traffic100%, 전용 runtime DB/session v1을 사용한다.
전용 migration1회·HTTP20개·maintenance dry-run1회/삭제0 통과, private16테이블64행 fingerprint/head
보존·staging spec 유지·익명403·domain 준비 HTML 유지 확인. 새 demo에는 방문 공간2/결재1/피드백1.
서비스 이미지는 75d5e8a 그대로이며 새 도구 커밋으로 재빌드했다고 표현하지 않는다.
합성 공용 자료의 실제 적용/HTTP 검증도 완료했다(아래). 실제 HMAC 상호 검증·demo backup/정리 운영·
최종 브라우저/domain QA·공개는 남아 있다.

[합성 공용 자료](demo-common-fixtures.md)는 PR #52 exact-head CI 5개/자체 리뷰/병합 후 실제 적용했다.
규정3/조항10/합성 COMPANY 일정48, password credential0, 실제 방문자 HTTP7개를 확인했다.
11월 합성 휴무 BLOCKED/선택 불가, 타운홀 CAUTION/선택 가능이며 정책 content hash가 일치했다.
최종 공간3/결재1/피드백1, private16테이블64행/head/fingerprint 불변이다. 이미지 재배포/AI/공개 전환 없음.

다음 작은 단위는 [demo 백업 프로필](demo-backup-profile.md)이다. 기존 staging 동작을 유지하고
새 demo migration Secret v1/전용 schema만 선택하는 도구와 회귀를 준비한다.
추가 인증 사용 범위 승인 후 실제 demo dump/격리 restore1회도 성공했다.
backup `20261023T015811Z-653f204f`, 55,567bytes/16테이블85행/schema·data·ACL·sequence·head 비교 통과,
임시 컨테이너 제거와 파일 권한/해시·원본 private64행/demo3·1·1 보존을 독립 확인했다.
다음은 [정리 리허설 계획](demo-retention-rehearsal.md)이다. 실제 삭제/추가 Job 실행/예약은 아직 하지 않았다.

아래 전용 신원 전환 미실행 설명은 credential 설정 직후 기록이다.

최신: [전용 credential 설정](demo-credential-setup.md#실제-초기-설정-결과--2026-10-23)은
추가 비용/인증 승인과 사용자 직접 입력 후 실제 성공했다. 새 Secret v1 ENABLED 3개와 실제
두 역할의 TLS pooler 인증/private SELECT 거부를 확인했다. 기존 서비스/Job은 아직 전용 신원으로
전환하지 않았다. 다음 [격리 배포 계획](demo-isolated-rollout.md)은 offline 준비이며 실제
migration Job 생성·실행/서비스·maintenance 전환은 별도 확인 후 수행한다.

아래 NOLOGIN/빈 Secret 및 credential 미실행 설명은 초기 기반 적용 당시 기록이다.

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

## 2026-10-24 후속 실제 모델·제품 배포

UI #65, 보안 키 입력 #66, 라이브 라우팅/CSP 준비 #67을 자체 리뷰·CI 통과 후 병합했다.
포트폴리오 별도 저장소 #35도 KO/EN 사례와 화면을 갱신해 검증·병합했다. 라이브 링크는 아직 없다.
제품 main 508bada의 비공개 staging 배포와 기본 smoke4개가 성공했다.
기존 키로 경비 합성 요청 2건의 실제 모델 추출을 확인했으며 자세한 범위는
[제한된 모델 점검](expense-model-smoke.md)을 따른다. 공개 AI 활성화나 전체 정확도 검증 완료를 뜻하지 않는다.
