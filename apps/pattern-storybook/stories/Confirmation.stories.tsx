import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { Alert, Button, ConfirmationDialog } from '@jhworks/pattern/react';
import { expect, userEvent, within } from 'storybook/test';

const meta = { title: 'JHW Pattern/Overlay/Confirmation', component: ConfirmationDialog,
  args: { open: false, title: '합성 초안을 제출할까요?', description: '금액과 문서 내용을 확인해주세요. 이 예제는 업무 API를 호출하지 않습니다.', confirmLabel: '확인하고 제출', onCancel: () => {}, onConfirm: () => {} },
} satisfies Meta<typeof ConfirmationDialog>;
export default meta;
type Story = StoryObj<typeof meta>;
function Demo({ busy = false, long = false }: { busy?: boolean; long?: boolean }) {
  const [open, setOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  return <><Button onClick={() => setOpen(true)}>합성 확인 창 열기</Button>
    <ConfirmationDialog open={open} title="합성 초안을 제출할까요?" description="합성 정보만 사용하며 업무 API는 호출하지 않습니다." confirmLabel="확인하고 제출" busy={busy} onCancel={() => setOpen(false)} onConfirm={() => { setOpen(false); setConfirmed(true); }}>
      <p>CES 합성 경비 · 170,000원 · v1</p>
      {long && <p>{'금액과 원본 증빙을 별도로 확인해주세요. '.repeat(45)}</p>}
    </ConfirmationDialog>
    {confirmed && <Alert tone="success">합성 예제 확인 완료</Alert>}
  </>;
}
export const Default: Story = { render: () => <Demo /> };
export const Pending: Story = { render: () => <Demo busy /> };
export const LongContent: Story = { render: () => <Demo long /> };
export const Keyboard: Story = { render: () => <Demo />, play: async ({ canvasElement }) => {
  const canvas = within(canvasElement);
  const trigger = canvas.getByRole('button', { name: '합성 확인 창 열기' });
  await userEvent.click(trigger);
  const cancel = canvas.getByRole('button', { name: '취소' });
  await expect(cancel).toHaveFocus();
  await userEvent.tab({ shift: true });
  await expect(canvas.getByRole('button', { name: '확인하고 제출' })).toHaveFocus();
  // Synthetic key events do not perform native dialog Escape defaults.
  // Playwright verifies a real Escape key against the same static build.
  await userEvent.click(cancel);
  await expect(trigger).toHaveFocus();
  await userEvent.click(trigger);
  await userEvent.click(canvas.getByRole('button', { name: '확인하고 제출' }));
  await expect(canvas.getByRole('status')).toHaveTextContent('합성 예제 확인 완료');
} };
