'use client';

import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { DemoRoleSwitcher } from '@/components/demo-entry';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { AppShell } from '@/components/app-shell';
import { AIReviewPanel } from '@/components/ai-review-panel';
import {
  ApprovalCommandDialog,
  type ApprovalCommandName,
  type ApprovalCommandSnapshot,
} from '@/components/approval-command-dialog';
import { LeaveSubmitAgentPanel } from '@/components/leave-submit-agent-panel';
import { StatusBadge } from '@/components/status-badge';
import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Approval, BusinessTripDetails, LeaveDetails } from '@/lib/types';
import { approvalTypeLabels } from '@/lib/approval-labels';
import { ExpenseSummary } from '@/components/expense-summary';
import { ExpenseChecksPanel } from '@/components/expense-checks';

type Command = ApprovalCommandName;

const lineStatusLabels = {
  WAITING: '대기 전',
  PENDING: '결재 대기',
  APPROVED: '승인',
  REJECTED: '반려',
} as const;

const costLabels = {
  transportation: '교통비',
  lodging: '숙박비',
  meals: '식비',
  other: '기타',
} as const;

const leaveUnitLabels = {
  FULL_DAY: '종일 연차',
  HALF_DAY_AM: '오전 반차',
  HALF_DAY_PM: '오후 반차',
} as const;

export default function ApprovalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const leaveRunId = searchParams.get('leaveRunId');
  const from = searchParams.get('from');
  // Only known list scopes can influence navigation; never accept a return URL.
  const listHref = from === 'mine' || from === 'assigned'
    ? `/approvals?scope=${from}#${encodeURIComponent(`approval-${id}`)}`
    : '/approvals';
  const { employee } = useCurrentEmployee();
  const { configuration } = useDemoConfiguration();
  const [approval, setApproval] = useState<Approval | null>(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);
  const [confirmation, setConfirmation] = useState<ApprovalCommandSnapshot | null>(null);
  const commandInFlight = useRef(false);

  const loadApproval = useCallback(() => {
    apiFetch<Approval>(`/approvals/${id}`)
      .then(setApproval)
      .catch((caught: unknown) => {
        setError(getUserErrorMessage(caught, '결재 문서를 불러오지 못했습니다.'));
      });
  }, [id]);

  useEffect(loadApproval, [loadApproval]);

  const pendingLine = useMemo(
    () => approval?.lines.find((line) => line.status === 'PENDING') ?? null,
    [approval],
  );
  const isAuthor = employee?.id === approval?.author.id;
  const isApprover = employee?.id === pendingLine?.approver.id;

  const requestCommand = (command: Command) => {
    if (!approval || commandInFlight.current) return;
    if (command === 'reject' && !comment.trim()) {
      setError('반려 사유를 입력해주세요.');
      return;
    }
    setError(null);
    setConfirmation({
      command,
      id: approval.id,
      title: approval.title,
      amount: approval.amount,
      version: approval.version,
      comment,
    });
  };

  const runCommand = async () => {
    if (!approval || !confirmation || commandInFlight.current) return;
    if (approval.id !== confirmation.id || approval.version !== confirmation.version) {
      setConfirmation(null);
      setError('문서가 변경되었습니다. 최신 내용을 확인한 뒤 다시 시도해주세요.');
      return;
    }
    commandInFlight.current = true;
    setIsActing(true);
    setError(null);
    try {
      const updated = await apiFetch<Approval>(
        `/approvals/${confirmation.id}/${confirmation.command}`,
        {
          method: 'POST',
          body: JSON.stringify({
            version: confirmation.version,
            ...(confirmation.command === 'approve' || confirmation.command === 'reject'
              ? { comment: confirmation.comment }
              : {}),
          }),
        },
      );
      setApproval(updated);
      setComment('');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '업무 상태를 변경하지 못했습니다.'));
    } finally {
      commandInFlight.current = false;
      setIsActing(false);
      setConfirmation(null);
    }
  };

  if (!approval) {
    return (
      <AppShell>
        <div className="empty-card">{error ?? '결재 문서를 불러오는 중입니다.'}</div>
      </AppShell>
    );
  }

  const trip = approval.details.kind === 'BUSINESS_TRIP' ? approval.details : null;
  const leave = approval.details.kind === 'LEAVE' ? approval.details : null;

  return (
    <AppShell>
      <ApprovalCommandDialog
        snapshot={confirmation}
        busy={isActing}
        onCancel={() => {
          if (!commandInFlight.current) setConfirmation(null);
        }}
        onConfirm={runCommand}
      />
      <header className="detail-header">
        <Link className="text-button" href={listHref}>
          ← 목록으로
        </Link>
        <div className="detail-title-row">
          <div>
            <div className="row-meta">
              <span>{approvalTypeLabels[approval.type]}</span>
              <span>·</span>
              <span>v{approval.version}</span>
            </div>
            <h1>{approval.title}</h1>
          </div>
          <StatusBadge status={approval.status} />
        </div>
      </header>

      {configuration?.enabled && isAuthor && approval.status === 'PENDING' && employee && (
        <section className="next-step-notice" aria-label="체험 다음 단계">
          <div>
            <strong>제출했어요. 이제 결재자가 되어 확인해 보세요.</strong>
            <p>같은 체험 공간에서 역할을 바꿔 승인하거나 반려할 수 있습니다.</p>
          </div>
          <DemoRoleSwitcher currentRole={employee.role} label="결재자로 전환해 계속하기" />
        </section>
      )}
      <div className="detail-layout">
        <article className="document-card">
          <section>
            <p className="eyebrow">PURPOSE</p>
            <h2>업무 내용</h2>
            <p className="document-copy">{approval.content || '작성된 내용이 없습니다.'}</p>
          </section>

          {trip && <TripDetails trip={trip} amount={approval.amount} />}
          {approval.details.kind === 'EXPENSE' && (
            <ExpenseSummary expense={approval.details} amount={approval.amount} />
          )}
          {leave && <LeaveRequestDetails leave={leave} />}
          {approval.type === 'EXPENSE' && (
            <ExpenseChecksPanel
              key={`${approval.id}-${approval.version}`}
              approvalId={approval.id}
              version={approval.version}
              status={approval.status}
            />
          )}

          {error && <p className="error-banner">{error}</p>}

          {isAuthor && approval.status === 'REJECTED' && (
            <div className="action-panel danger-soft">
              <div>
                <strong>반려된 문서입니다.</strong>
                <p>과거 결재 의견을 유지한 채 새로운 초안으로 전환할 수 있습니다.</p>
              </div>
              <button
                className="primary-button"
                disabled={isActing}
                onClick={() => requestCommand('revise')}
                type="button"
              >
                다시 수정하기
              </button>
            </div>
          )}

          {isApprover && approval.status === 'PENDING' && (
            <div className="decision-panel">
              <label>
                <span>결재 의견</span>
                <textarea
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="반려 시 사유는 필수입니다."
                  rows={3}
                  value={comment}
                />
              </label>
              <div className="button-row">
                <button
                  className="danger-button"
                  disabled={isActing}
                  onClick={() => requestCommand('reject')}
                  type="button"
                >
                  반려
                </button>
                <button
                  className="primary-button"
                  disabled={isActing}
                  onClick={() => requestCommand('approve')}
                  type="button"
                >
                  승인
                </button>
              </div>
            </div>
          )}
        </article>

        <aside className="context-column">
          <section className="context-card">
            <p className="eyebrow">AUTHOR</p>
            <strong>{approval.author.name}</strong>
            <span>{approval.author.position}</span>
          </section>
          <section className="context-card">
            <p className="eyebrow">TIMELINE</p>
            <dl>
              <div>
                <dt>작성</dt>
                <dd>{formatDate(approval.createdAt)}</dd>
              </div>
              <div>
                <dt>제출</dt>
                <dd>{formatDate(approval.submittedAt)}</dd>
              </div>
              <div>
                <dt>결정</dt>
                <dd>{formatDate(approval.decidedAt)}</dd>
              </div>
            </dl>
          </section>
          <section className="context-card">
            <p className="eyebrow">APPROVAL HISTORY</p>
            {approval.lines.length === 0 && <span>아직 제출되지 않았습니다.</span>}
            {approval.lines.map((line) => (
              <div className="history-item" key={line.id}>
                <strong>
                  {line.round}회차 · {line.approver.name}
                </strong>
                <span>{lineStatusLabels[line.status]}</span>
                {line.comment && <p>{line.comment}</p>}
              </div>
            ))}
          </section>
        </aside>

        {isAuthor && approval.status === 'DRAFT' && (
          <section className="draft-review-flow">
            <AIReviewPanel approval={approval} canReview onApprovalUpdated={setApproval} />
            {leave && leaveRunId ? (
              <LeaveSubmitAgentPanel
                approval={approval}
                onApprovalUpdated={setApproval}
                runId={leaveRunId}
              />
            ) : (
              <div className="action-panel">
                <div>
                  <strong>내용을 확인하고 제출하세요</strong>
                  <p>
                    제출하면 지정된 결재자에게 전달됩니다. 초안은 제출 전까지 수정할 수 있습니다.
                  </p>
                </div>
                <div className="button-row">
                  <Link className="secondary-button" href={`/approvals/${approval.id}/edit`}>
                    수정
                  </Link>
                  <button
                    className="primary-button"
                    disabled={isActing}
                    onClick={() => requestCommand('submit')}
                    type="button"
                  >
                    제출
                  </button>
                </div>
              </div>
            )}
          </section>
        )}
        {isAuthor && leave && leaveRunId && approval.status !== 'DRAFT' && (
          <section className="draft-review-flow">
            <LeaveSubmitAgentPanel
              approval={approval}
              onApprovalUpdated={setApproval}
              runId={leaveRunId}
            />
          </section>
        )}
      </div>
    </AppShell>
  );
}

const TripDetails = ({ trip, amount }: { trip: BusinessTripDetails; amount: number | null }) => (
  <section>
    <p className="eyebrow">BUSINESS TRIP</p>
    <h2>출장 정보</h2>
    <dl className="detail-grid">
      <div>
        <dt>출장지</dt>
        <dd>{trip.destination || '-'}</dd>
      </div>
      <div>
        <dt>고객사</dt>
        <dd>{trip.clientName || '-'}</dd>
      </div>
      <div>
        <dt>기간</dt>
        <dd>
          {trip.startDate || '-'} → {trip.endDate || '-'}
        </dd>
      </div>
      <div>
        <dt>예상 금액</dt>
        <dd>{formatCurrency(amount)}</dd>
      </div>
      <div className="wide">
        <dt>방문 목적</dt>
        <dd>{trip.visitPurpose || '-'}</dd>
      </div>
    </dl>
    <div className="cost-summary">
      {Object.entries(trip.costBreakdown ?? {}).map(([key, value]) => (
        <span key={key}>
          {costLabels[key as keyof typeof costLabels]} <strong>{formatCurrency(value)}</strong>
        </span>
      ))}
    </div>
  </section>
);

const LeaveRequestDetails = ({ leave }: { leave: LeaveDetails }) => (
  <section>
    <p className="eyebrow">LEAVE REQUEST</p>
    <h2>휴가 정보</h2>
    <dl className="detail-grid">
      <div>
        <dt>휴가 단위</dt>
        <dd>{leaveUnitLabels[leave.leaveUnit]}</dd>
      </div>
      <div>
        <dt>차감 일수</dt>
        <dd>{leave.requestedDays ? `${leave.requestedDays}일` : '-'}</dd>
      </div>
      <div>
        <dt>기간</dt>
        <dd>
          {leave.startDate || '-'} → {leave.endDate || '-'}
        </dd>
      </div>
      <div className="wide">
        <dt>휴가 사유</dt>
        <dd>{leave.reason || '-'}</dd>
      </div>
      <div className="wide">
        <dt>인수인계</dt>
        <dd>{leave.handoverNote || '-'}</dd>
      </div>
    </dl>
  </section>
);
