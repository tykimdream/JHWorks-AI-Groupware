# 서명 토큰 만료 계약

## 문제와 완료 조건
세션과 AI 쓰기 확인 토큰은 발급 시 iat/exp를 넣지만 기존 decoder는 해당 claim의 존재를 요구하지 않는다.
서명이 유효하더라도 만료 claim이 없는 token은 거부해야 한다. 서명 키 없이 token을 위조할 수 있다는 의미는 아니다.
정상 발급 token과 기존 결재/AI 확인 흐름은 유지한다. 누락·잘못된 시간·만료·다른 용도 token을 거부하고
HTTP 401 이후 보호된 쓰기가 발생하지 않아야 한다. 새 인증정보나 공개 인증 endpoint는 만들지 않는다.

## 대안과 선택
Cookie Max-Age만으로는 복사된 token의 서버 만료를 보장하지 못한다. 별도 Redis/세션 저장소는
폐기·방문자 수명 관리에는 유용하지만 이 claim 검증 공백을 해결하는 데 필요하지 않다.
기존 PyJWT의 서명/시간 검증을 유지하고 필수 claim 및 정수 시간/양수 수명 계약을 공통 decoder에 적용한다.
DB migration·새 의존성·환경변수·키 교체 없이 적용한다.

## 공개 데모 격리 조사
현재 인증은 employee ID이며 workspace/session 레코드는 없다.
결재 목록/상세/수정은 작성자와 결재자 ID를 검증하고 개인 연차는 employee ID로 제한한다.
반면 조직 API는 모든 활성 부서를 반환하고 팀 휴가는 department ID, 회사 일정/규정은 공유 범위다.
방문자마다 계정만 만들거나 부서만 나누는 것으로 전체 격리를 완료했다고 표현할 수 없다.
다음 단위에서 서버 관리 workspace membership, 수명, 원자 쓰기 예산 및 모든 조회/Tool 경계를 함께 검증한다.
공개 bootstrap은 아직 없으며 새 인증·공개 권한 적용 전 사용자 확인을 받는다.

## 검증 기록
- 구현 전 decoder 회귀: 시간 claim 누락 8건, 문자열/boolean 허용 8건을 재현했다(16 failed/16 passed; signed 대상 선택).
- 최초 HTTP 테스트의 cache-control 기대값은 실제 private, no-store 계약에 맞게 수정했다.
  최초 실행 중 Windows socketpair WinError 10014가 2건 발생했다. 이후 같은 실행 경로의 관련 45개는 통과했다.
- 최종 테스트에는 필수 claim 4개 누락, 만료/미래/0수명/잘못된 시간 타입, 용도 교차 재사용,
  정상 발급 수명 및 보호된 GET/POST 401을 포함한다. 최종 전체 API는 342 passed / 10 skipped / 35.93초다(신규 69개 포함).
  PostgreSQL 10개는 로컬 DB 환경이 없어 skip되며 별도 CI에서 확인한다.
- Ruff 검사와 strict mypy 126 files 통과. DB migration과 신규 의존성은 없다.
공개 domain은 정적 준비 화면, 기존 private staging과 AI=false는 유지한다.

## 한계와 학습
서명은 변조 방지이고 만료 검증은 별도 계약이다. 로그아웃은 현재 Cookie 삭제이며 복사된 정상 token의
즉시 폐기를 보장하지 않는다. 서버 관리 방문자 수명/폐기, 격리, 쓰기 예산은 이 수정의 완료 범위가 아니다.
면접 질문: Cookie 만료와 JWT exp는 어떤 차이인가? 서명된 token에도 schema 검증이 필요한 이유는?
