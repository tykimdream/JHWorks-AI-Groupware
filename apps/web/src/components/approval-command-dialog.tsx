'use client';

import { ConfirmationDialog } from '@/components/confirmation-dialog';
import { formatCurrency } from '@/lib/format';

export type ApprovalCommandName = 'submit' | 'approve' | 'reject' | 'revise';
export interface ApprovalCommandSnapshot {
  command: ApprovalCommandName;
  id: string;
  title: string;
  version: number;
  amount: number | null;
  comment: string;
}

const labels = {
  submit: {
    title: '결재 제출 확인',
    action: '확인하고 제출',
    note: '직속 관리자에게 제출합니다. 제출 후 결재 진행 상태로 전환됩니다.',
  },
  approve: {
    title: '결재 승인 확인',
    action: '확인하고 승인',
    note: '검토한 내용으로 승인합니다. 증빙 참조가 있다면 원본을 별도로 확인해 주세요.',
  },
  reject: {
    title: '결재 반려 확인',
    action: '확인하고 반려',
    note: '입력한 사유와 함께 작성자에게 문서를 돌려보냅니다.',
  },
  revise: {
    title: '재작성 확인',
    action: '확인하고 재작성',
    note: '이전 결재 이력을 보존하고 수정 가능한 초안으로 전환합니다.',
  },
};

export function ApprovalCommandDialog({
  snapshot,
  busy,
  onCancel,
  onConfirm,
}: {
  snapshot: ApprovalCommandSnapshot | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  const copy = snapshot ? labels[snapshot.command] : labels.submit;
  return (
    <ConfirmationDialog
      open={snapshot !== null}
      title={copy.title}
      description={copy.note}
      confirmLabel={copy.action}
      busy={busy}
      onCancel={onCancel}
      onConfirm={() => void onConfirm()}
    >
      {snapshot && (
        <dl className="command-preview">
          <div>
            <dt>문서</dt>
            <dd>{snapshot.title}</dd>
          </div>
          {snapshot.amount !== null && (
            <div>
              <dt>금액</dt>
              <dd>{formatCurrency(snapshot.amount)}</dd>
            </div>
          )}
          <div>
            <dt>확인 버전</dt>
            <dd>v{snapshot.version}</dd>
          </div>
          {snapshot.comment && (
            <div>
              <dt>의견</dt>
              <dd>{snapshot.comment}</dd>
            </div>
          )}
        </dl>
      )}
    </ConfirmationDialog>
  );
}
