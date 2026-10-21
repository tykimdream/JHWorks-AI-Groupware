# 첫 작업: Cookie 인증 쓰기 요청의 출처 검증

상태: 로컬 구현·검증 완료, 2026-10-21. 아래 기준을 구현 전에 정의했다.
최종 API 150개(기존 111+신규 39), browser E2E 8개 통과. 외부 TLS/proxy 검증은 대기 중이다.

## 문제와 완료 조건

`app/main.py`의 CORS는 허용한 origin의 응답 읽기를 제어하지만 쓰기 서비스의 실행 전 출처 검증은 없다.
SameSite=Lax만으로 같은 site의 다른 origin까지 신뢰해서는 안 된다. 로그인 CSRF도 있으므로 로그인과
로그아웃을 포함한 POST/PUT/PATCH/DELETE 등 안전하지 않은 모든 HTTP method에 공통 검사를 둔다.

- Origin이 있으면 설정한 frontend origin과 scheme/hostname/effective port가 같아야 한다.
- Origin이 없으면 Referer의 origin을 검사한다. 잘못된 Origin을 Referer로 우회하지 않는다.
- null/복수/비정상 origin, 유사 도메인, 다른 port, 사용자 정보가 포함된 URL을 거부한다.
- production/prod는 두 header가 모두 없으면 거부한다. 개발 CLI와 기존 테스트의 무헤더 호출은 유지한다.
- 읽기와 OPTIONS preflight는 유지한다. 거부는 403, 안정적인 코드와 request ID를 반환한다.
- 거부된 로그인은 cookie를 만들지 않고, 거부된 업무 쓰기는 DB를 변경하지 않는다.

## 대안과 선택

1. CORS/SameSite만 유지: 서버에서 쓰기 출처를 보장하지 못해 제외.
2. 세션에 결합한 CSRF token: 강한 대안이지만 발급·회전·클라이언트 전달 계약이 추가된다.
3. 고정한 frontend origin 검증: 현재 단일 웹 클라이언트와 Cookie API에 맞고 새 의존성이 없어 선택.

Host/X-Forwarded-Host를 신뢰 기준으로 사용하지 않는다. Reverse proxy의 host 처리와 무관하게
`JHWORKS_FRONTEND_ORIGIN`을 신뢰 기준으로 고정한다. 외부 OAuth callback, webhook, native client가
필요해지면 인증 방식과 예외 경로를 별도 검토한다. 전체 출처 검증을 끄는 옵션은 추가하지 않는다.

## 핵심 원리와 한계

브라우저 script는 Origin/Referer를 임의의 신뢰 origin으로 바꿀 수 없다. 서버가 처리 전에 이를 확인한다.
비브라우저 client는 header를 위조할 수 있으므로 이것은 인증·인가나 rate limit의 대체가 아니다.
XSS로 신뢰 화면 안에서 실행되는 script도 막지 못한다. production의 CLI 쓰기는 신뢰 Origin을 명시해야 한다.
proxy가 header를 지우면 안전하게 거부되므로 staging에서 로그인·저장·제출을 검증해야 한다.

기준: [OWASP CSRF Prevention — origin 검증](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#using-standard-headers-to-verify-origin).

## 학습과 운영 검증

- 실습: 로컬 로그인 요청에 외부 Origin을 붙여 403과 Set-Cookie 없음, 정상 Origin으로 200을 비교한다.
- 면접 질문: CORS가 왜 쓰기를 막는 인증 장치가 아닌가? site와 origin은 어떻게 다른가?
  SameSite와 Origin 검증을 함께 두는 이유는 무엇인가?
- 기업 운영에서는 허용 origin 변경을 설정 배포로 리뷰하고 403 비율·request ID를 관측한다.
  header 누락과 공격을 구분하되 원문 Referer/쿠키/token은 로그에 남기지 않는다.
- 회귀 테스트는 fake provider와 synthetic SQLite를 사용한다. 실제 TLS/proxy/browser 보안 검증과 구분한다.
