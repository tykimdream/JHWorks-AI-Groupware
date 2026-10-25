import type { Meta, StoryObj } from '@storybook/react-vite';
import { Alert, Button, EmptyState } from '@jhworks/pattern/react';
const meta = { title: 'JHW Pattern/Feedback/Alert', component: Alert,
  argTypes: { tone: { control: 'select', options: ['info', 'danger', 'success'] }, children: { control: false } },
  args: { tone: 'info', title: '아직 제출하지 않았습니다', children: '초안을 확인한 뒤 별도로 제출해주세요.' },
} satisfies Meta<typeof Alert>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Information: Story = {};
export const Error: Story = { args: { tone: 'danger', title: '초안을 저장하지 못했습니다', children: <><p>입력은 유지했습니다. 연결을 확인한 뒤 다시 시도해주세요.</p><Button variant="secondary">다시 시도</Button></> } };
export const Success: Story = { args: { tone: 'success', title: '초안을 저장했습니다', children: '내용을 확인한 뒤 제출해주세요.' } };
export const LongMessage: Story = { args: { tone: 'danger', title: '같은 문서가 다른 곳에서 변경되었습니다', children: '현재 입력은 그대로 유지했습니다. 최신 버전과 변경 내용을 비교하고 다시 저장해주세요. 새로고침을 선택하면 이 탭의 임시 입력을 이어쓸 수 있지만 기본 문서 버전이 다르면 자동으로 덮어쓰지 않습니다.' } };
export const Empty: Story = { render: () => <EmptyState title="작성한 결재가 없습니다." description="첫 초안을 작성해 업무 흐름을 시작해보세요."><Button>새 초안 작성</Button></EmptyState> };
