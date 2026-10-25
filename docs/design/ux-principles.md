# JHWorks UX 원칙과 적용 — 2026-10-25

공식 제품·디자인 시스템 문서를 비교하고, 대표 경비 업무에 적용할 기준을 정리한다.
개선 효과나 사용자 성공률은 아직 측정하지 않았으며 아래는 제품 가설과 구현 기준이다.

| 근거 | 배울 원칙 | JHWorks 적용 |
| --- | --- | --- |
| [Linear: calmer interface](https://linear.app/now/behind-the-latest-design-refresh) | 핵심 작업에 시각적 우선순위를 주고 탐색·장식을 정돈한다 | AI가 꺼진 공개 홈의 큰 비활성 입력창 대신 지금 가능한 경비 작성과 다음 행동을 앞세운다 |
| [Atlassian: content](https://atlassian.design/foundations/content), [messages](https://atlassian.design/foundations/content/designing-messages) | 명료하고 짧고 일관된 문구, 상태와 행동의 연결 | Draft 대신 초안, 저장과 제출의 차이를 설명하고 확인 창에 실제 문서·금액을 보여 준다 |
| [Atlassian: spotlight card](https://atlaskit.atlassian.com/packages/design-system/spotlight/components/spotlight-card) | 짧은 발견 메시지, 투어는 최대 3단계, 닫기 제공 | 첫 체험 가이드는 작성·제출·승인 3단계. 비모달로 업무를 막지 않고 건너뛰기·다시 보기·Esc를 제공한다 |
| [Carbon: tooltip](https://carbondesignsystem.com/components/tooltip/usage/) | 툴팁은 보충 설명에 사용하고 필수 정보는 보이게 유지한다 | 초안 저장·제출의 차이는 본문에서 안내하고, 도움말에는 보충 설명만 넣는다. hover·focus·터치와 Esc를 지원한다 |
| [Carbon: onboard](https://www.carbondesignsystem.com/building-experiences/onboard) | 첫 로그인에서 의미 있는 첫 결과로 안내한다 | 가이드 마지막 행동은 경비 양식 열기이며 데이터 저장·제출을 자동 실행하지 않는다 |
| [Tailwind: theme variables](https://tailwindcss.com/docs/theme) | 토큰을 제품에서 소비하는 API로 다룬다 | tokens.json에서 CSS·문서 목록을 생성하고 실제 화면과 JHW Pattern이 같은 패키지를 사용한다 |

## 제품에서의 적용

- 공개 홈: 경비 작성 CTA 하나를 중심으로 단계와 보조 탐색을 배치한다. 비활성 AI 입력창은 제거하고 AI 제공 범위는 짧게 표시한다.
- 첫 방문 가이드: 브라우저 단위 버전 키 `jhworks.guide.v1`만 저장한다. 개인 정보·업무 문서는 저장하지 않는다. 스토리지 사용 불가 시에도 닫기·다시 보기가 동작한다.
- 가이드는 비모달이며 자동 표시 때 포커스를 빼앗지 않는다. 사용자가 직접 다시 열면 닫기에 포커스를 둔다. 안내 안에서 Esc를 누르면 닫고 트리거로 돌아간다.
- 실제 쓰기는 기존 명시적 확인·서버 권한·version 검증을 유지한다. 가이드 이동은 폼을 여는 것까지이며 문서를 자동 생성하지 않는다.
- JHW Pattern `/pattern`: 시작 방법, 토큰 검색, 실제 Button·Badge·도움말 미리보기와 코드, 업무 패턴과 접근성을 공개한다.

## 패키지 범위

`packages/pattern`은 토큰과 Button·Badge를 제공한다. 도움말과 가이드는 제품 내부에서 검증 중이며 패키지의 안정 API로 내보내지 않는다.
초기 패키지는 private·UNLICENSED 상태로 외부 게시를 막는다. 로컬 pack과 소비 앱 확인 뒤 이름·소유권·라이선스·접근성 계약을 확정한다.
Tailwind를 새로 도입하거나 CSS 전체를 일괄 교체하지 않는다. 기존 토큰 별칭으로 단계적 전환을 지원한다.

## 검증할 결과

1. 처음 방문한 사람이 경비 작성 → 제출 → 역할 전환 → 승인을 별도 설명 없이 마칠 수 있는가.
2. 가이드가 업무를 가리지 않고 닫기·다시 보기·키보드·스토리지 차단 환경에서 동작하는가.
3. 패키지 토큰과 문서 값이 일치하고, 폼 안의 예제 버튼이 의도치 않은 제출을 일으키지 않는가.
4. PC·모바일에서 가독성·넘침·포커스를 유지하는가.

실사용 시간·이탈·완료율 측정은 후속 사용자 평가로 남긴다. 자동 회귀 통과를 사용성 향상 수치로 바꾸지 않는다.
