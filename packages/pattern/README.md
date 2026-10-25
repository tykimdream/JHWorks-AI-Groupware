# JHW Pattern

JHWorks에서 사용하는 의미 기반 토큰과 UI 컴포넌트의 workspace 미리보기입니다.
**npm 미배포 · private 패키지 · 라이선스 미확정** 상태입니다.

## 사용

```sh
pnpm add @jhworks/pattern@workspace:*
```

```tsx
import '@jhworks/pattern/tokens.css';
import '@jhworks/pattern/components.css';
import { Button, Badge } from '@jhworks/pattern/react';

<Button onClick={save}>초안 저장</Button>
<Badge tone="info">결재 대기</Badge>
```

React 19를 peer dependency로 사용합니다. 전역 스타일은 앱 진입점에서 한 번 불러옵니다.
`Button`은 기본 `type="button"`이며 폼 제출에는 `type="submit"`을 명시합니다.
`variant`: primary / secondary / danger / ghost.
`Badge tone`: neutral / info / success / danger / warning. 상태에는 색과 글자를 함께 씁니다.
HTML 링크에는 `buttonClass('primary')`를 사용할 수 있습니다.

## 원본과 생성물

`tokens.json` → `pnpm --filter @jhworks/pattern build` → `tokens.css`, `legacy.css`, `catalog.js`.
`pnpm --filter @jhworks/pattern check`가 원본과 생성물이 어긋나면 실패합니다.
현재 앱의 레거시 변수 이름은 별도 `legacy.css`의 alias로 유지합니다. 일반 소비 앱에서는 이 파일을 불러올 필요가 없습니다. 모든 기존 CSS를 이전했다고 주장하지 않습니다.

## 배포 준비

`pnpm --filter @jhworks/pattern pack --pack-destination ./artifacts/pattern`으로 로컬 tarball을 만듭니다.
외부 게시 전 패키지 이름·소유권, 라이선스, 공개 API, 접근성·키보드 동작과 소비 앱 검증을 확정해야 합니다.
게시용 토큰·계정 권한을 이 저장소에 넣지 않습니다. 이 패키지는 업무 API나 비밀정보에 의존하지 않습니다.
