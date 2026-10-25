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

저장소 루트에서 `pnpm --filter @jhworks/pattern pack --pack-destination "$PWD/artifacts/pattern"`으로 로컬 tarball을 만듭니다.
외부 게시 전 패키지 이름·소유권, 라이선스, 공개 API, 접근성·키보드 동작과 소비 앱 검증을 확정해야 합니다.
게시용 토큰·계정 권한을 이 저장소에 넣지 않습니다. 이 패키지는 업무 API나 비밀정보에 의존하지 않습니다.

## 폼과 상태

```tsx
import { Field, Input, Select, Textarea, Alert, EmptyState, ConfirmationDialog } from '@jhworks/pattern/react';

<Field id="expense-amount" label="실제 지출 금액" description="원 단위" error={error} required>
  <Input type="number" value={amount} onChange={changeAmount} />
</Field>
<Field label="비용 구분"><Select>{options}</Select></Field>
<Field label="업무 목적"><Textarea rows={3} /></Field>
<Alert tone="danger" title="저장하지 못했습니다">입력은 유지했습니다. 다시 시도해주세요.</Alert>
<EmptyState title="작성한 결재가 없습니다." description="첫 초안을 작성해보세요." />
```

- `Field`는 하나의 Input/Select/Textarea에 라벨·설명·오류 ID를 연결합니다. 고정 ID가 필요하면 Field에 `id`를 전달합니다. Field 내부에서는 Field의 ID를 사용합니다.
- 오류는 입력칸의 `aria-invalid`와 `aria-describedby`로 연결합니다. 외부 `aria-describedby`도 유지합니다. required/disabled를 Field에서 제어하거나 각 입력에 직접 지정할 수 있습니다.
- Input/Select/Textarea는 native props·이벤트·React19 ref를 전달합니다. Field 없이 쓰면 직접 라벨 또는 aria-label을 제공해야 합니다.
- Alert의 `tone`: info/success는 status, danger는 alert입니다. 다시 시도 같은 다음 행동을 children으로 제공할 수 있습니다. 상태를 알리지 않을 맥락에서는 role을 명시하세요.
- EmptyState는 데이터가 없다는 사실과 다음 행동을 안내하며 로딩·오류의 대체 문구로 사용하지 않습니다.

```tsx
<ConfirmationDialog
  open={open}
  title="초안을 제출할까요?"
  description="내용을 확인한 뒤 제출해주세요."
  confirmLabel="확인하고 제출"
  onCancel={() => setOpen(false)}
  onConfirm={submit}
  busy={pending}
>
  <p>합성 경비 · 170,000원 · v1</p>
</ConfirmationDialog>
```

ConfirmationDialog는 **읽기 전용 사실을 확인하는** 대화상자입니다. 본문에 입력·링크 등 추가 포커스 대상을 넣는 범용 폼 모달은 지원하지 않습니다. 취소 초기 포커스, 두 footer 버튼의 Tab 순환, Esc 취소, 닫은 뒤 트리거 포커스 복원과 busy 중 버튼/닫기 차단을 제공합니다. open과 busy는 소비자가 제어하며 버튼 클릭만으로 내부에서 업무 API를 호출하지 않습니다.

경비 폼·폼 오류·빈 목록·제출/승인·이동 확인과 `/pattern` 문서의 예제가 동일한 export를 소비합니다. Next.js·업무 API·인증 세션에 의존하지 않습니다. styles는 namespace를 가진 CSS로 제공해 소비 앱에 Tailwind 설치를 요구하지 않고, 제품의 배치에는 기존 Tailwind bridge를 사용합니다.
