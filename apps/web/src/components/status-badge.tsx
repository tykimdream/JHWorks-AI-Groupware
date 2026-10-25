import { Badge } from '@jhworks/pattern/react';
import type { ApprovalStatus } from '@/lib/types';

const labels: Record<ApprovalStatus, string> = {
  DRAFT: '초안',
  PENDING: '결재 대기',
  APPROVED: '승인',
  REJECTED: '반려',
};

export const StatusBadge = ({ status }: { status: ApprovalStatus }) => (
  <Badge
    tone={
      status === 'APPROVED'
        ? 'success'
        : status === 'REJECTED'
          ? 'danger'
          : status === 'PENDING'
            ? 'info'
            : 'neutral'
    }
    className={`status-badge status-${status.toLowerCase()}`}
  >
    {labels[status]}
  </Badge>
);
