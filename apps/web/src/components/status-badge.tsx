import type { ApprovalStatus } from '@/lib/types';

const labels: Record<ApprovalStatus, string> = {
  DRAFT: '임시저장',
  PENDING: '결재 대기',
  APPROVED: '승인',
  REJECTED: '반려',
};

export const StatusBadge = ({ status }: { status: ApprovalStatus }) => (
  <span className={`status-badge status-${status.toLowerCase()}`}>{labels[status]}</span>
);

