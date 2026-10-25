'use client';

import { Button } from '@jhworks/pattern/react';
import { useEffect, useId, useRef } from 'react';
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
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const open = snapshot !== null;
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      element.showModal();
      cancel.current?.focus();
    } else if (!open && element.open) {
      element.close();
    }
  }, [open]);
  const copy = snapshot ? labels[snapshot.command] : labels.submit;
  return (
    <dialog
      ref={dialog}
      className="approval-command-dialog"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      aria-busy={busy}
      onKeyDown={(event) => {
        if (event.key !== 'Tab' || busy) return;
        if (event.shiftKey && event.target === cancel.current) {
          event.preventDefault();
          confirm.current?.focus();
        } else if (!event.shiftKey && event.target === confirm.current) {
          event.preventDefault();
          cancel.current?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <p className="eyebrow">REVIEW & CONFIRM</p>
      <h2 id={titleId}>{copy.title}</h2>
      <p id={descriptionId}>{copy.note}</p>
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
      <div className="button-row">
        <Button ref={cancel} variant="secondary" type="button" disabled={busy} onClick={onCancel}>
          취소
        </Button>
        <Button ref={confirm} type="button" disabled={busy} onClick={() => void onConfirm()}>
          {busy ? '처리 중…' : copy.action}
        </Button>
      </div>
    </dialog>
  );
}
