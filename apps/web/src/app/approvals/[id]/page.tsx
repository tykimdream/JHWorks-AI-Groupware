'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { AppShell } from '@/components/app-shell';
import { StatusBadge } from '@/components/status-badge';
import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Approval, BusinessTripDetails } from '@/lib/types';

type Command = 'submit' | 'approve' | 'reject' | 'revise';

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

export default function ApprovalDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const { employee } = useCurrentEmployee();
  const [approval, setApproval] = useState<Approval | null>(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

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

  const runCommand = async (command: Command) => {
    if (!approval) {
      return;
    }
    if (command === 'reject' && !comment.trim()) {
      setError('반려 사유를 입력해주세요.');
      return;
    }

    const labels: Record<Command, string> = {
      submit: '이 Draft를 직속 관리자에게 제출할까요?',
      approve: '이 결재를 승인할까요?',
      reject: '입력한 사유로 이 결재를 반려할까요?',
      revise: '반려 문서를 다시 수정 가능한 Draft로 전환할까요?',
    };
    if (!window.confirm(labels[command])) {
      return;
    }

    setIsActing(true);
    setError(null);
    try {
      const updated = await apiFetch<Approval>(`/approvals/${approval.id}/${command}`, {
        method: 'POST',
        body: JSON.stringify({
          version: approval.version,
          ...(command === 'approve' || command === 'reject' ? { comment } : {}),
        }),
      });
      setApproval(updated);
      setComment('');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '업무 상태를 변경하지 못했습니다.'));
    } finally {
      setIsActing(false);
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

  return (
    <AppShell>
      <header className="detail-header">
        <button className="text-button" onClick={() => router.push('/approvals')} type="button">
          ← 목록으로
        </button>
        <div className="detail-title-row">
          <div>
            <div className="row-meta">
              <span>{approval.type === 'BUSINESS_TRIP' ? '출장 신청' : '일반 결재'}</span>
              <span>·</span>
              <span>v{approval.version}</span>
            </div>
            <h1>{approval.title}</h1>
          </div>
          <StatusBadge status={approval.status} />
        </div>
      </header>

      <div className="detail-layout">
        <article className="document-card">
          <section>
            <p className="eyebrow">PURPOSE</p>
            <h2>업무 내용</h2>
            <p className="document-copy">{approval.content || '작성된 내용이 없습니다.'}</p>
          </section>

          {trip && <TripDetails trip={trip} amount={approval.amount} />}

          {error && <p className="error-banner">{error}</p>}

          {isAuthor && approval.status === 'DRAFT' && (
            <div className="action-panel">
              <div>
                <strong>제출 준비가 되었나요?</strong>
                <p>서버가 현재 조직 정보에서 직속 관리자를 다시 계산합니다.</p>
              </div>
              <div className="button-row">
                <Link className="secondary-button" href={`/approvals/${approval.id}/edit`}>
                  수정
                </Link>
                <button
                  className="primary-button"
                  disabled={isActing}
                  onClick={() => runCommand('submit')}
                  type="button"
                >
                  제출
                </button>
              </div>
            </div>
          )}

          {isAuthor && approval.status === 'REJECTED' && (
            <div className="action-panel danger-soft">
              <div>
                <strong>반려된 문서입니다.</strong>
                <p>과거 결재 의견을 유지한 채 새로운 Draft로 전환할 수 있습니다.</p>
              </div>
              <button
                className="primary-button"
                disabled={isActing}
                onClick={() => runCommand('revise')}
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
                  onClick={() => runCommand('reject')}
                  type="button"
                >
                  반려
                </button>
                <button
                  className="primary-button"
                  disabled={isActing}
                  onClick={() => runCommand('approve')}
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
              <div><dt>작성</dt><dd>{formatDate(approval.createdAt)}</dd></div>
              <div><dt>제출</dt><dd>{formatDate(approval.submittedAt)}</dd></div>
              <div><dt>결정</dt><dd>{formatDate(approval.decidedAt)}</dd></div>
            </dl>
          </section>
          <section className="context-card">
            <p className="eyebrow">APPROVAL HISTORY</p>
            {approval.lines.length === 0 && <span>아직 제출되지 않았습니다.</span>}
            {approval.lines.map((line) => (
              <div className="history-item" key={line.id}>
                <strong>{line.round}회차 · {line.approver.name}</strong>
                <span>{lineStatusLabels[line.status]}</span>
                {line.comment && <p>{line.comment}</p>}
              </div>
            ))}
          </section>
        </aside>
      </div>
    </AppShell>
  );
}

const TripDetails = ({ trip, amount }: { trip: BusinessTripDetails; amount: number | null }) => (
  <section>
    <p className="eyebrow">BUSINESS TRIP</p>
    <h2>출장 정보</h2>
    <dl className="detail-grid">
      <div><dt>출장지</dt><dd>{trip.destination || '-'}</dd></div>
      <div><dt>고객사</dt><dd>{trip.clientName || '-'}</dd></div>
      <div><dt>기간</dt><dd>{trip.startDate || '-'} → {trip.endDate || '-'}</dd></div>
      <div><dt>예상 금액</dt><dd>{formatCurrency(amount)}</dd></div>
      <div className="wide"><dt>방문 목적</dt><dd>{trip.visitPurpose || '-'}</dd></div>
    </dl>
    <div className="cost-summary">
      {Object.entries(trip.costBreakdown ?? {}).map(([key, value]) => (
        <span key={key}>{costLabels[key as keyof typeof costLabels]} <strong>{formatCurrency(value)}</strong></span>
      ))}
    </div>
  </section>
);
