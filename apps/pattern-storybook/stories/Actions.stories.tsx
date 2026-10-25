import type { Meta, StoryObj } from '@storybook/react-vite';
import { Badge, Button } from '@jhworks/pattern/react';
import { expect, fn, userEvent, within } from 'storybook/test';

const meta = {
  title: 'JHW Pattern/Actions/Button', component: Button,
  args: { children: '초안 저장', onClick: fn() },
  argTypes: { variant: { control: 'select', options: ['primary', 'secondary', 'danger', 'ghost'] } },
} satisfies Meta<typeof Button>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Primary: Story = { play: async ({ canvasElement, args }) => {
  const button = within(canvasElement).getByRole('button', { name: '초안 저장' });
  await userEvent.click(button);
  await expect(args.onClick).toHaveBeenCalledTimes(1);
  await expect(button).toHaveAttribute('type', 'button');
} };
export const Secondary: Story = { args: { variant: 'secondary', children: '계속 작성' } };
export const Danger: Story = { args: { variant: 'danger', children: '반려' } };
export const Pending: Story = { args: { disabled: true, 'aria-busy': true, children: '저장 중…' }, play: async ({ canvasElement, args }) => {
  await expect(within(canvasElement).getByRole('button')).toBeDisabled();
  await expect(args.onClick).not.toHaveBeenCalled();
} };
export const LongLabel: Story = { args: { children: '변경 내용을 확인하고 초안으로 저장하기' } };
export const Statuses: Story = { render: () => <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
  <Badge>초안</Badge><Badge tone="info">결재 대기</Badge><Badge tone="success">승인</Badge><Badge tone="danger">반려</Badge>
</div> };
