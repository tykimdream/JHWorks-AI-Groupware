# 공개 전 프레임워크 보안 수정 — 2026-10-24

공개 준비 중 GitHub Dependabot에 현재 Next 16.3.8의 critical/high 공지가 추가된 것을 확인했다.
공개 IAM/Hosting 적용 전에 제품 배포를 멈추고 Next 및 eslint-config-next를 수정 버전 16.4.1로 맞췄다.
새 이미지가 아직 배포되지 않은 기존 staging/demo가 수정됐다고 표현하지 않는다.

- [typed array use cache RCE 공지](https://github.com/advisories/GHSA-673q-mjm6-r5xr)
- [SVG 이미지 최적화 RCE 공지](https://github.com/advisories/GHSA-2464-fhr4-w9xw)
- [Server Actions DoS 공지](https://github.com/advisories/GHSA-p3m5-59mp-jv5r)
- [Zod 메모리 소모 공지](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)

Zod는 eslint-plugin-react-hooks → eslint-config-next의 개발 의존성이다.
4.x 중 취약 범위만 4.6.6으로 고정하는 pnpm override를 추가했고 기존 다른 major에는 적용하지 않는다.
취약 기능을 현재 앱이 노출했는지와 별개로 공개할 이미지에서는 공지된 수정 버전을 사용한다.
침해가 있었다는 증거를 발견한 것은 아니며 단순 패키지 경고를 침해 사고로 표현하지 않는다.

검증: pnpm audit에서 info/low/moderate/high/critical 모두0, lint·타입·production build,
운영 standalone CSP·경비 정산 desktop/mobile 4개, 일반 브라우저32개와 공개 모드2개를 확인한다.
이번 변경은 의존성과 Next가 갱신한 AGENTS 제목 단계뿐이며 제품 기능·IAM·AI 활성화·삭제 설정은 바꾸지 않는다.
공개 전 새 고정 이미지 배포와 실제 HTTPS 도메인 검증을 별도로 완료해야 한다.
