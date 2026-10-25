# 스타일 도구의 역할과 전환 범위

## 서로 다른 역할

| 도구 | 이 프로젝트에서의 역할 |
| --- | --- |
| JHW Pattern 토큰·문서 | 색상·간격·상태·업무 패턴의 원칙과 사용법. 실제 제품과 같은 토큰과 컴포넌트를 소비한다. |
| Tailwind CSS | 앱 화면의 레이아웃·반응형·상태 스타일을 JSX 가까이에서 작성하는 구현 도구. 디자인 토큰을 대체하지 않는다. |
| CSS 패키지 | 토큰과 Button·Badge의 기본 스타일을 특정 앱 빌드 도구에 의존하지 않고 제공한다. |
| Storybook (아직 미도입) | 컴포넌트를 앱·인증·서버 없이 독립적으로 재현하고 상태·키보드·상호작용을 검증하는 작업 환경. |

Storybook과 Pattern 문서는 대체 관계가 아니다. Pattern은 선택의 이유와 업무 규칙을 설명하고,
Storybook은 같은 컴포넌트의 실제 상태를 재현한다. Button·Badge에서 폼 입력·확인 창 등으로
공개 API가 확장될 때 상태별 stories와 상호작용 검증을 추가하고 정적 배포하는 것이 다음 도입 기준이다.
도입 여부를 묻는 단계에서 별도 호스팅이나 유료 서비스를 추가하지 않는다.

## Tailwind 적용

기존 앱은 전역 CSS를 사용했다. 첫 토큰 추출에서는 기존 화면 회귀를 줄이기 위해 같은 스타일 체계를 유지했다.
현재 앱은 Tailwind 4와 PostCSS를 도입했으며, 사이드바와 하단 계정 영역부터 유틸리티로 전환했다.
전체 앱의 CSS 이전이 완료된 상태는 아니다.

- 진입점: `apps/web/src/app/tailwind.css`, PostCSS 설정: `apps/web/postcss.config.mjs`.
- 기존 클래스와 이름이 겹치지 않도록 `tw:` prefix를 사용한다.
- Preflight는 제외한다. 기존 폼·목록·헤더의 전역 리셋을 일괄 변경하지 않는다.
- `@theme inline`이 JHW 토큰을 참조한다. 같은 색상 값을 별도로 복제하지 않는다.
- 전환한 영역의 기존 선택자는 삭제한다. `!important`로 기존 규칙을 덮어쓰지 않는다.
- 공통 폼의 font 상속은 base layer에 두어 유틸리티의 명시적인 글자 크기를 허용한다.

```tsx
<div className="tw:flex tw:gap-4 tw:bg-jhw-surface tw:text-jhw-text">
  <span className="tw:text-jhw-muted">초안 저장 후 제출할 수 있어요.</span>
</div>
```

사이드바는 PC에서 화면 높이에 맞추고 메뉴만 스크롤한다. 하단 안내·역할 전환·프로필은 하나의 footer에
묶어 계정 동작이 항상 보이게 한다. 모바일은 일반 문서 흐름으로 바꾸고 메뉴를 가로 스크롤한다.
PC 1024/1280/1440/1920 폭과 600/720/900 높이에서 넘침·하단 간격을 검증한다.

공식 근거: [Tailwind Next.js 설치](https://tailwindcss.com/docs/installation/framework-guides/nextjs),
[Preflight 선택적 제외](https://tailwindcss.com/docs/preflight#disabling-preflight),
[다른 변수를 참조하는 theme](https://tailwindcss.com/docs/theme#referencing-other-variables),
[Storybook stories](https://storybook.js.org/docs/writing-stories/index).
