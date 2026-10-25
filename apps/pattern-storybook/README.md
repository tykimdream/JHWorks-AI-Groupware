# JHW Pattern Storybook

실제 제품과 같은 `@jhworks/pattern/react` 및 토큰/CSS를 소비하는 독립 React/Vite 환경입니다. Next.js, 업무 API, 인증 세션, 실제 직원 자료, AI 키에 의존하지 않습니다.

저장소 루트에서 실행합니다.

```sh
pnpm storybook
pnpm type-check:storybook
pnpm build:storybook
pnpm test:storybook
```

23개 story가 Button/Badge, Field/Input/Select/Textarea, Alert/EmptyState, ConfirmationDialog의 기본·오류·필수·disabled·pending·긴 문구·키보드 상태를 재현합니다. native 입력은 부모 Field의 라벨/설명/오류와 연결됩니다. 모든 데이터와 금액은 합성 예제입니다.

정적 테스트는 `/storybook/` 하위 경로에서 전체 story를 열어 렌더·play 결과·자동 axe WCAG2 A/AA 및2.1 AA 검사·가로 넘침·무API호출을 확인합니다. 확인 창의 실제 Escape/Tab/취소 포커스 복원과 pending 닫기 차단, manager/docs 직접 링크·새로고침·브랜드 asset도 검증합니다. 자동 검사 통과가 전체 접근성 준수나 사람 사용성 평가를 뜻하지 않습니다.

Storybook의 합성 userEvent Esc는 브라우저의 native dialog 기본 동작을 실행하지 않으므로 play에서는 취소 버튼을 사용하고 실제 Escape는 Playwright keyboard로 별도 확인합니다.

`storybook-static/`은 Git에서 제외하고 CI artifact로 제공합니다. `core.disableTelemetry`와 CLI 옵션으로 Storybook telemetry를 비활성화했습니다. 빌드의 큰 문서 chunk 경고와 패키지의 use client 지시문 무시 경고는 독립 Vite 환경에 대한 것이며 제품 Next 번들에 Storybook을 포함하지 않습니다.

배포 절차·공개 조건은 [운영 문서](../../docs/design/storybook.md)를 따릅니다. npm은 private·미게시 상태입니다.
