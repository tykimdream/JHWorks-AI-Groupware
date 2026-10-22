# 비공개 staging 업무 검증

## 문제와 완료 조건

배포 health 성공만으로 앱 로그인·권한·업무 transaction 성공을 주장할 수 없다.
2026-10-22 사용자가 private fixture의 비밀번호를 직접 설정했고 도구가
department 1 / employee 3 / credential 3 / leave account 3 생성 성공을 출력했다.
이 비밀번호와 DB password hash는 개발 도구의 출력이나 저장소에 수집하지 않는다.

완료 조건은 실제 로그인 cookie로 일반 결재·휴가의 draft→submit→approve,
비참여자 조회/승인 403, stale version 409, 휴가 pending→used와 calendar 확인이다.
검증 전 세 계정 신원·빈 결재 목록·휴가 잔액을 검사하고, 실패 시 자동 재시도/삭제하지 않는다.

## 선택과 원리

- DB에 최종 상태를 직접 쓰는 방식은 인증·인가·트랜잭션을 우회하므로 제외했다.
- Playwright 화면 검증은 private ingress 접속 경로가 별도로 필요하다. 이번 단계는 HTTP 계약을 먼저 검증한다.
- 기존 httpx 개발 의존성과 실제 command API를 사용한다. 새 라이브러리나 유료 자원을 추가하지 않는다.
- Google ID token은 `X-Serverless-Authorization`, 앱 session은 별도 cookie jar를 쓴다.
  Cloud Run ingress 인증과 앱 사용자 인가라는 서로 다른 경계를 함께 통과해야 한다.
- 실제 사용자 입력 비밀번호는 TTY getpass로 한 번 받아 메모리에서만 사용한다.
  session secret을 읽거나 토큰을 위조하지 않는다. HTTP redirect는 따라가지 않는다.

## 실행 계약

`uv run --frozen python -m app.ops.staging_workflow --commit <현재 배포된 full SHA>`

기본 명령은 service preflight만 실행한다. 실제 업무 검증은 --apply를 명시하고
고정 프로젝트의 private/AI-off/revision/max=2 검사와 쓰기 범위 표시 뒤
숨김 비밀번호를 **사용자가 직접** 입력한다. 일반 텍스트 확인 칸은 제거했다.
생성한 fixture 전용 비밀번호를 사용하고 GCP/Supabase 비밀번호를 재사용하지 않는다.
비밀번호·cookie·Google token을 인자/환경변수/파일/채팅으로 전달하지 않는다.

일반 결재 1건·휴가 결재 1건을 남기고 해당 연도 첫 12월 월요일의 합성 연차 1일을 사용한다.
쓰기 요청은 자동 재전송하지 않는다. timeout/중간 실패 시 이미 저장됐을 수 있으므로
기록된 stage와 승인 문서를 확인하고 재실행하지 않는다. 이 도구는 초기 fixture 전용이며
동시 실행을 허용하는 멱등 배치가 아니다. 출력은 고정 check 이름과 결과뿐이다.

## 검증 범위와 남은 일

로컬 Windows cp949 기본 모드에서 API **235 passed / 19.51초**,
Ruff app/tests/alembic, strict mypy app/tests 114 source files 통과.
추가한 5개 테스트는 실제 router 정상 흐름/재실행 거부, 잘못된 비밀번호의 쓰기 차단,
redirect/timeout 무재시도, CLI 오류 원문 비노출을 확인했다.

로컬 재현은 실제 FastAPI router·인증·SQLAlchemy 서비스와 SQLite fixture를 통과해야 한다.
외부 실행 전에는 PostgreSQL 업무 검증 완료로 표시하지 않는다. 순차 stale version 검사는
실제 동시 transaction 충돌 시험을 대체하지 않는다. UI·AI·부하·재해 복구도 별도 단계다.
기업에서는 격리된 테스트 tenant/수명이 제한된 계정과 실행별 멱등 키, 감사 가능한 결과 보존을
추가한다. 현재 private 초기 검증의 잔액/빈 목록 검사만으로 동시 실행을 제어한다고 주장하지 않는다.

면접에서는 “Google 인증을 통과했는데 앱 API는 왜 401인가?”, “409 재시도가 결재를 중복 처리할 수
있는가?”, “HTTP 성공과 DB 정합성 검증은 어떻게 다른가?”를 현재 경계로 설명할 수 있어야 한다.

비밀번호 교체·실제 실패 단계는 [교체 기록](../operations/private-staging-password.md)에 구분했다.
