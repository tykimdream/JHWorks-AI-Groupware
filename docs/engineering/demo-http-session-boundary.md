# 실제 서비스 간 HTTP 세션 경계 검증

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

현재 이 문서는 실행 전 계획이다. 실제 원격 HTTP 검증은 결과가 생기기 전까지 미완료다.

## 로컬 검증

- 전용 회귀15개: 고정 대상/config drift 거부, 수신 쿠키 이름, 동일 키·잘못된401 원인·
  교차 요청 후 만료 거부, 응답 유실·cleanup·중복 실행 차단, 실제 API 양방향 서명 거부.
- 전체 API: `uv run --frozen pytest` — 477 passed/29 PostgreSQL skipped(로컬 DB 미실행).
- `uv run --frozen ruff check app tests alembic`, `uv run --frozen mypy app tests` 통과.
- 새 의존성·API 계약·migration·서비스 배포 변경은 없다. PostgreSQL 회귀는 CI에서 확인한다.
