# 라이브 앱 연결 준비 — 2026-10-24

## 현재 상태와 변경

`groupware.pikan.dev`는 아직 준비 화면이다. 이 변경은 배포 준비만 하며 IAM/Hosting을 적용하지 않는다.
`deploy/firebase/firebase.live.json`은 빈 app-public을 사용하고 모든 요청을 기존 서울 리전 `jhworks-demo`로 전달한다.
준비 화면용 `firebase.json`과 정적 파일은 보존한다. 두 설정을 동시에 적용하지 않는다.
API는 같은 서비스의 Next rewrite를 거쳐 내부 API 컨테이너에 연결된다. Firebase가 전달하는 `__session` 쿠키를 유지한다.

준비 화면의 CSP는 스크립트를 전부 차단하므로 라이브 설정에는 복사하지 않는다.
앱의 Proxy가 매 HTML 요청에 임의 nonce를 생성하고 Next의 요청/응답 CSP에 함께 전달한다.
루트 레이아웃을 동적 렌더링하여 빌드 시점의 nonce나 HTML을 재사용하지 않는다.
운영 script-src는 nonce/strict-dynamic을 사용하며 unsafe-inline/unsafe-eval을 허용하지 않는다.
기존 React style 속성 때문에 style-src에는 unsafe-inline이 필요하다. 개발에서만 HMR의 eval과 websocket을 허용한다.
응답에 no-store, nosniff, no-referrer, frame-ancestors none, 장치 권한 차단을 적용한다.
CDN HTML 캐시를 사용하지 않는 트레이드오프가 있다. 공개 앱 호출은 기존 서비스의 과금/사용량에 포함된다.

## 검증

- 실제 production standalone 서버에서 desktop/mobile CSP·로그인 및 CES 정산→승인 4개 통과.
- 연속 HTML 요청의 nonce가 다르고 응답 CSP와 HTML script nonce가 일치한다.
- 운영 CSP에 eval/인라인 스크립트 허용이 없으며 로그인부터 홈까지 CSP 위반이 없다.
- 브라우저 CI에서 production build 및 같은 검증을 수행한다.
- fixture의 AI는 합성 응답이며 실제 모델 품질 검증은 아니다.

## 기존 원격 상태 (읽기 전용 조회)

2026-10-24 Cloud Shell에서 demo 리비전 `jhworks-demo-75d5e8a98fb2-3c51785fafdb`,
min=0/max=1/concurrency=4, demo 전용 runtime 계정, 서비스 IAM에 binding 없음과 Scheduler PAUSED를 확인했다.
키 원문은 조회하지 않았다. 이 결과는 새 제품 이미지 배포나 공개 전환 성공의 증거가 아니다.

## 적용 전 확정할 범위

1. 최신 main의 CI 통과 및 고정 이미지 digest 준비, 기존 demo 전용 DB/세션 Secret 참조 유지.
2. 비공개 demo 서비스에 새 리비전을 적용하고 인증된 smoke로 대표 흐름을 확인.
3. 공개 직전 기존 IAM 정책 백업 후 **jhworks-demo 하나에만** allUsers/roles.run.invoker를 추가.
4. `deploy/firebase`에서 `firebase deploy --project jhworks-staging-tykimdream --config firebase.live.json --only hosting` 실행.
5. 실제 HTTPS 도메인에서 체험 시작·역할 전환·경비 작성/승인·피드백, 두 방문자 격리,
   세션 쿠키·캐시·CSP·만료/한도를 확인한 후 포트폴리오 live 링크를 활성화.

3~4는 새로운 익명 접근을 허용하는 실제 공개 전환이다. 준비된 리비전·설정과 영향 범위를 제시하고 사용자 승인을 받은 뒤 적용한다.
이 문서를 근거로 공개 승인이 있었다고 간주하지 않는다. 새 서비스/DB/상시 인스턴스/예약을 추가하지 않는다.
AI 키 입력은 별도 작업이며 현 public demo AI=false 정책은 그대로다. 실제 공개 AI는 별도 호출 예산/설계 검증이 필요하다.

## 복귀

문제가 있으면 준비 화면용 `firebase.json`을 같은 사이트에 다시 배포하고 demo의 allUsers invoker binding을 제거한다.
이 경우도 이미 발급된 세션/데이터가 삭제되는 것은 아니다. 이전 이미지가 EXPENSE 데이터를 읽지 못할 수 있으므로 무작정 옛 API로 되돌리지 않는다.
공개 전환 전 IAM/Hosting 이전 상태와 새 리비전·이미지 digest를 실제 실행 기록으로 남긴다.

설계 근거: [Next.js 공식 CSP 가이드](https://nextjs.org/docs/app/guides/content-security-policy).
