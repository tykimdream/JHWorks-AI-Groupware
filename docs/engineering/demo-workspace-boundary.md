# 방문자 작업 공간 경계 — 구현 단위 1

## 문제·완료 조건
공개 계정 하나를 공유하면 작성한 결재와 연차가 다른 방문자에게 보인다. 부서를 나누기만 하면
조직 API, 관리자 관계, 만료된 세션과 재시도 쓰기 누적을 제한하지 못한다.
서버 관리 workspace에 속한 합성 직원만 해당 공간에 접근하도록 기반을 만든다.
정상 private 직원(workspace 없음)은 기존 동작을 유지한다. 이 변경은 공개 bootstrap을 만들지 않는다.

- workspace의 DB 시간 기준 만료/비활성화 시 정상 서명 세션도 401.
- 소속 부서/관리자 관계가 어긋나면 fail closed. 조직 목록은 해당 부서 1개.
- 보호된 POST/PATCH/PUT/DELETE 시도는 workspace 전체 수명 쓰기 예산을 원자적으로 선점.
- 실패한 업무 시도도 예산에 남고, 소진 시 429. GET과 logout은 계속 가능.
- 두 workspace의 결재 목록/상세/수정/결재 및 Agent run 교차 접근 거부.
- SQLite 회귀와 PostgreSQL 실제 connection 동시성, additive migration 검사.
- 기존 계정/실제 데이터는 바꾸거나 새로 만들지 않는다.

## 대안과 선택
공유 read-only demo는 단순하지만 작성/승인 경험을 제공하지 못한다.
방문자별 DB/schema는 runtime DDL 권한과 정리/연결 관리 비용이 크다.
전체 업무 모델을 범용 tenant 시스템으로 재작성하는 대신 기존 employee 소유권과 department 범위를
재사용하고 nullable workspace FK, 서버 수명/상한, 인증 경계 검사를 추가한다.
이는 일반 기업 multi-tenant/RLS 구현이 아니다. 전역 회사 일정·규정은 추후 공개용 합성 read-only
자료만 허용하는 별도 공개 환경 계약이 필요하다. private 데이터와 섞인 환경을 공개하지 않는다.

## 예산 의미와 한계
쓰기 예산은 허용된 보호 API의 안전하지 않은 HTTP 메서드 시도 수이며 AI의 읽기 성격 POST도 포함한다.
업무 성공 수/LLM token 예산이 아니다. admission 직후 업무가 실패해도 선점 commit은 유지한다.
재시도는 추가 예산을 사용한다. 클라이언트 헤더/body로 workspace/상한을 정할 수 없다.
공간 생성 전체 예산, 읽기 요청 제한, AI 비용 한도, 데이터 삭제/초기화 정책, 공개 전용 인증 모드와
화면/쿠키/Hosting rewrite는 아직 다음 단계다. 이 기반만으로 공개 준비 완료라고 표시하지 않는다.
DB 장애는 503으로 닫고 비밀 내용을 응답에 포함하지 않는다.

## 운영·검증
DB migration은 아직 외부에 적용하지 않는다. 현재 실제 staging head는 c84f2a19d6e0이다.
실제 계정/새 권한/공개 전환은 수행하지 않는다. 정상 private 회귀와 로컬/CI 결과를 아래에 추가한다.

## 로컬 검증 결과
- workspace API/격리/예산 회귀 18개: 결재·Agent·조직·팀 일정·개인 Tool 격리와 provider 호출 전 예산 거부.
- disposable SQLite migration: 기존 employee 모든 기존 필드 보존·nullable FK/index·빈 공간 downgrade/
  재-upgrade·공간 존재 시 downgrade 거부 1 passed (5.27초).
- 전체 API 361 passed / 13 skipped (34.07초). PostgreSQL 13개는 전용 로컬 DB가 없어 skip이며 CI에서 실행한다.
- Ruff/strict mypy 131 files 통과. 최초 1 failed/13 passed는 테스트 Cookie의 domain 없는 수동 삽입이
  실제 Set-Cookie 삭제 domain과 달랐던 fixture 문제였고 testserver.local로 수정했다.
- [ADR 0002](../adr/0002-demo-workspace-admission.md)에 선택과 rollback 제한을 기록한다.
외부 DB/Cloud Run에는 이 변경을 적용하지 않았으며 실제 방문자 인증·부하·정리 결과는 없다.

CI에는 PostgreSQL 8 worker/24 attempt/limit 5의 실제 경합, 잠금 중 폐기, 잘못된 결재선 SQL 필터를 추가했다. 실행 결과는 PR의 정확한 head checks를 따른다.
