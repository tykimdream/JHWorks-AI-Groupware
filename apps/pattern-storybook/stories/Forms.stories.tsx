import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-vite';
import { Button, Field, Input, Select, Textarea } from '@jhworks/pattern/react';
import { expect, userEvent, within } from 'storybook/test';

const meta = { title: 'JHW Pattern/Forms/Field', component: Field,
  argTypes: {
    label: { control: 'text' }, description: { control: 'text' }, error: { control: 'text' },
    required: { control: 'boolean' }, disabled: { control: 'boolean' },
    children: { control: false, description: '라벨을 연결할 Input, Select 또는 Textarea 한 개' },
  },
  args: { label: '실제 지출 금액', description: '이미 지출한 금액을 원 단위로 입력합니다.', children: <Input type="number" defaultValue="170000" /> },
} satisfies Meta<typeof Field>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Default: Story = {};
export const Required: Story = { args: { required: true } };
export const Invalid: Story = { args: { error: '0원보다 큰 실제 지출 금액을 입력해주세요.', children: <Input type="number" defaultValue="0" /> }, play: async ({ canvasElement }) => {
  const input = within(canvasElement).getByRole('spinbutton', { name: '실제 지출 금액' });
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  await expect(input).toHaveAccessibleDescription(/0원보다 큰 실제 지출 금액/);
} };
export const Disabled: Story = { args: { disabled: true } };
export const LongDescription: Story = { args: { description: '합성 예제입니다. 환불이나 별도 지출은 동일한 금액이어도 다른 거래일 수 있습니다. 실제 원본과 업무 목적을 확인하고 금액을 입력해주세요.' } };
export const SelectExample: Story = { args: { label: '비용 구분', description: undefined, children: <Select defaultValue=""><option value="">선택해주세요</option><option value="TRANSPORTATION">교통비</option><option value="MEALS">식비</option></Select> } };
export const TextareaExample: Story = { args: { label: '업무 목적', description: '결재자가 지출의 목적을 이해할 수 있도록 작성합니다.', children: <Textarea rows={4} defaultValue="CES 고객 미팅 참석을 위한 합성 교통비" /> } };
function EditableExample() {
  const [value, setValue] = useState('');
  const [checked, setChecked] = useState(false);
  return <div style={{ display: 'grid', gap: 20, maxWidth: 480 }}>
    <Field label="업무 목적" description="합성 정보만 입력하세요." error={checked && !value.trim() ? '업무 목적을 입력해주세요.' : undefined}>
      <Textarea value={value} onChange={(event) => setValue(event.target.value)} />
    </Field>
    <Button onClick={() => setChecked(true)}>입력 확인</Button>
  </div>;
}
export const Validation: Story = { render: () => <EditableExample />, play: async ({ canvasElement }) => {
  const canvas = within(canvasElement);
  await userEvent.click(canvas.getByRole('button', { name: '입력 확인' }));
  const input = canvas.getByRole('textbox', { name: '업무 목적' });
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  await userEvent.type(input, 'CES 합성 출장');
  await expect(input).not.toHaveAttribute('aria-invalid');
} };
