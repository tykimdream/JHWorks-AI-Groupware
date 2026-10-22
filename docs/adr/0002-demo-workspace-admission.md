# ADR 0002 — 서버 관리 demo workspace admission

상태: 채택(코드 기반), 외부 적용·공개 bootstrap 미완료.
날짜: 2026-10-22.

## 맥락
개인 포트폴리오의 작성/승인 체험은 공유 계정으로 제공하면 방문자 데이터가 섞인다.
기존 앱은 employee 소유권·department 팀 조회·서버 결재 상태 전이를 이미 검증한다.
전체 업무 모델의 범용 multi-tenant 재작성과 방문자별 DB/schema는 현재 범위에 비해 크다.

## 결정
DemoWorkspace와 Employee의 nullable FK를 사용한다. 기존 private 직원은 NULL로 호환한다.
서버 신원에서 공간을 찾고 DB wall clock의 epoch로 만료를 검사한다. 독점 부서와 같은 공간의
관리자만 허용하며 다른 공간/일반 직원이 그 부서에 들어오면 인증을 닫는다.
조직 목록과 결재 목록/상세/명령에도 공간 검사를 적용한다. 잘못 import된 결재선도 차단한다.
부서 내 혼합 여부 조회를 위해 (department_id, demo_workspace_id) index를 둔다.
이는 query 형태에 근거한 선택이며 성능 향상 수치는 측정하지 않았다.

보호된 unsafe HTTP 요청 시 SQL UPDATE ... WHERE writes_used < write_limit RETURNING으로
예산을 선점하고 업무 전 commit한다. DB 시간/활성 여부를 UPDATE에서 다시 검사하므로 동시 요청과
검사 후 만료·폐기에도 상한을 지킨다. 실패와 재시도도 차감한다. 예산은 공간 수명당 기본 20,
DB 제약 1~100이며 클라이언트가 정하지 않는다. 조회와 logout은 예산 소진 후에도 가능하다.

## 대안
공유 read-only demo는 간단하지만 작성/승인 체험이 없다. 방문자별 schema는 runtime DDL과 정리
복잡도가 생긴다. Redis는 현 DB 원자 갱신으로 해결 가능한 카운터를 위해 새 운영 서비스를 만든다.
전체 tenant/RLS는 일반 SaaS 운영 범위에서 재검토할 수 있지만 이 변경은 그 수준을 주장하지 않는다.

## 결과와 조건
공개 API나 방문자 생성은 추가하지 않는다. 실제 private DB migration/새 계정/권한 전환도 아직 없다.
향후 bootstrap은 고유 부서를 만들고 workspace와 직원/관리자를 같은 transaction에서 묶어야 한다.
정리/폐기는 먼저 workspace를 비활성화해야 하며 직원의 FK를 NULL로 바꿔 일반 계정으로 전환하면 안 된다.
공간이 한 개라도 있으면 migration downgrade를 거부해 보호 제거를 막는다. 기존 schema로의
애플리케이션 rollback은 구버전 API가 공개 visitor를 이해하지 못하므로 공개 차단부터 수행해야 한다.
요청 admission 후 진행 중인 읽기를 취소하지는 않는다.

전역 회사 일정·규정은 공개 환경에서 검토된 합성 read-only 내용만 사용한다. 공개 전용 인증 모드가
비공개 계정을 거부하고 생성 총량/읽기·AI 비용/정리 상한을 갖추기 전에는 외부 공개하지 않는다.
직접 DB 접근은 앱 권한 경계의 우회가 가능하며 DB RLS가 있는 것으로 표현하지 않는다.

## 검증
[구현·재현 기록](../engineering/demo-workspace-boundary.md).
면접에서 설명할 핵심은 분리된 선점 commit(실패도 차감), 원자 조건부 갱신과 멱등 업무 결과의
차이, Cookie/JWT 만료와 서버 workspace 수명의 차이다.
