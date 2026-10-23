# 실제 서비스 간 HTTP 세션 경계 검증

## 실제 실행 결과 — 2026-10-23 20:50 KST

사용자의 후속 실행 요청으로 앱 내부 Cloud Shell에서 아래 범위를1회 실행해 exit0을 확인했다.
PR [#61](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/61)은 exact head
`7ea7534a4fd6769d7da42f1ca3f31da6e9ca0036`의 CI5개 성공·자체 리뷰 COMMENT·reviewed/security
라벨 후 병합했다(main `2357ca4bfa02d3d5a4ea34d703549754c761b75e`). 독립적인 사람의 승인은 아니다.

| 검사 | 실제 결과 |
| --- | --- |
| 서비스/config 사전 조건 | 두 대상 통과, AI off·비공개 IAM 유지 |
| 정상 private/demo 세션 | 교차 요청 전후4회200, 정확한 합성 actor 일치 |
| demo→private, private→demo | 수신 쿠키 이름으로 전송, 서명 오류401 각1회 |
| logout / 무쿠키 | 각각2회200 / 2회401 |
| 요청·자격증명 사용 | HTTP13, private session Secret v1 읽기1, 기존 Google ID token1 |
| 합성 생성 | 방문 공간1, 업무 결재0/피드백0; 정상 demo 조회 예산2회 소비 |
| 보고서 | status passed/stage complete, 생성 결과 미확정false, cleanup 오류없음 |

관찰 시각 `2026-10-23T11:50:27.055641+00:00`.
합성 공간 `demo_37c1b661b3f14409b2ff5d13ae6c414c`, 만료 epoch `1792757126`.
만료 시각은 `2026-10-23 21:05:26 KST`다.
기존 TTL/보존 정책을 따르며 직접 삭제·만료 조정·정리 Job 실행은 하지 않았다.
키·JWT·cookie·응답 원문 출력/저장0이며 demo signing key/DB credential/직원 비밀번호는 읽지 않았다.

최초 metadata-only는 Cloud Shell 재연결 후 active 계정/토큰 연결 문제로 실패했다
(`11:46:46 UTC`, Secret0/ID token0/HTTP0). 기존 계정 선택과 브라우저 재연결을 갱신한 뒤
별도 preflight가 `11:48:59 UTC`에 통과했다. 실패 파일을 보존했고 실제 `--execute`는1회뿐이다.

고정 source archive SHA256 `440af1f6a6b77cef5cc560df70060c15ed1e1bddc1806728b730a76fda69c84e`,
실행 module SHA256 `30cd83138646d3ad7e7e8fb194206724e69b7442b920a49957dd84b0e5c23c08`.
원격 산출물은 `~/jhworks-http-boundary-7ea7534/`의 `preflight.json`,
`preflight-after-refresh.json`, `executed.json`, `verified.json`에 보존한다.
별도 프로세스로 Secret/HTTP 재접근 없이 보고서 전체 상태·건수·HTTP 상태 순서·source hash와
폴더0700/보고서0600을 대조했다. 결과 보고서 SHA256은
`d8c3e304867dafd066a290d9b02e0723cbc61094dfd4a3673f5fbddaca5db879`다.
읽기 전용 revision 재대조도 private `jhworks-staging-75d5e8a98fb2`,
demo `jhworks-demo-75d5e8a98fb2-3c51785fafdb`로 일치했다. 이번 도구 source로 앱을 재배포한 것은 아니다.

이 결과로 실행 계획 A2의 실제 HTTP 정상/상호 거부 조건을 충족했다. logout은 쿠키 삭제이며
서버 JWT 취소를 입증하지 않는다. 합성 공간만 사용했고 모든 private 업무 데이터의 fingerprint를
다시 계산한 것은 아니다. 최종 도메인/브라우저 QA·정리 주기·실패/누락 감지·공개는 후속이다.
아래는 실행 전 고정한 계획이다.

## 문제와 완료 조건

[실제 키 검증](demo-session-key-boundary.md)은 서명키 분리를 확인했지만 배포된 API가 올바른
키/쿠키/인증 경로를 사용하는지까지 검증하지 않았다. 이번 단위는 두 서비스의 정상 세션200과
상대 세션401을 실제 `/employees/me`로 비교한다.

쿠키 이름이 private `jhworks_session`/demo `__session`으로 다르므로 상대 세션도 **수신 서비스의
쿠키 이름**에 넣는다. 서명 거부의 오류 code/message를 확인하고, 교차 요청 후 양쪽 정상 세션을
다시200으로 확인해 쿠키 누락·직원 부재·만료 때문에 우연히401이 된 것을 성공으로 처리하지 않는다.

## 실행 범위

- 기존 두 private Cloud Run 서비스의 Ready revision/traffic100·전용 runtime/DB/session v1·AI off·
  origin/cookie/public-demo 모드와 서비스/프로젝트 IAM의 익명 grant 부재를 먼저 읽어 확인한다.
- 기본 실행은 metadata만 읽는다. `--execute`에서만 기존 Google ID token과 private session
  Secret `jhworks-session-secret` v1을1회 사용한다. demo signing key/DB credential/직원 비밀번호는 읽지 않는다.
- 기존 합성 private 작성자 `stg_author_001`에 대한60초 세션 JWT를 메모리에서 만들어 조회한다.
  공개 데모는 기존 `/demo/start`를1회 호출해 합성 공간1개를 만들고 서버가 발급한 cookie를 사용한다.
- 정상·교차·재확인·로그아웃·무쿠키 거부를 확인한다. 성공 경로 HTTP13개이며 업무 결재/휴가/피드백을 만들지 않는다.
  정상 demo 조회2회는 기존 요청 예산을 소비한다. 공간/직원/연차 계정 생성과 전체 생성 예산1회 소비는 명시적 변경이다.
- 키/token/cookie/응답 원문은 출력·저장하지 않는다. 합성 workspace ID/만료 시각·단계/상태/건수만 기록한다.
  고정 host 외 전송, redirect/proxy/자동 재시도·새 권한/배포/공개 전환은 하지 않는다.

## 실패와 반복 실행

`--output`을0600/exclusive create해 실행 전에 attempt를 남긴다. 이미 존재하면 cloud/Secret/HTTP에
접근하기 전에 중단한다. `/demo/start` 응답 유실은 생성 가능성 미확정으로 기록하고 재전송하지 않는다.
실패 시 확보한 세션의 logout을 best-effort로 한 번씩 시도하고 안전한 단계·오류 종류만 남긴다.
logout은 서버 workspace의 만료/보존을 변경하지 않는다. 생성한 공간은 기존 TTL/정리 정책을 따른다.
실패한 공간을 직접 삭제하거나 만료를 조정하지 않는다.

## 준비·적용 순서

1. 고정 source의 관련 회귀/lint/type/CI·리뷰를 완료한다.
2. 기본 metadata 점검으로 실제 대상이 준비된 계획과 일치하는지 확인한다.
3. 위 private key1회·합성 공간1개·HTTP 검증 범위를 확인하고 `--execute`를1회 실행한다.
4. 보고서·파일 권한·source hash를 Secret 재접근 없이 확인하고 실제 결과/한계를 기록한다.

위 순서에 따른 실제 결과는 문서 상단에 기록한다.

## 로컬 검증

- 전용 회귀15개: 고정 대상/config drift 거부, 수신 쿠키 이름, 동일 키·잘못된401 원인·
  교차 요청 후 만료 거부, 응답 유실·cleanup·중복 실행 차단, 실제 API 양방향 서명 거부.
- 전체 API: `uv run --frozen pytest` — 477 passed/29 PostgreSQL skipped(로컬 DB 미실행).
- `uv run --frozen ruff check app tests alembic`, `uv run --frozen mypy app tests` 통과.
- 새 의존성·API 계약·migration·서비스 배포 변경은 없다. PostgreSQL 회귀는 CI에서 확인한다.
