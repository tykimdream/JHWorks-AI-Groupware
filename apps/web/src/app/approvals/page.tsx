'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';

import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { AppShell } from '@/components/app-shell';
import { StatusBadge } from '@/components/status-badge';
import { ApiError, apiFetch } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/format';
import type { ApprovalListResponse } from '@/lib/types';
import { approvalTypeLabels } from '@/lib/approval-labels';

type Scope = 'mine' | 'assigned';

function ApprovalListContent() {
  const searchParams = useSearchParams();
  const { configuration } = useDemoConfiguration();
  const [scope, setScope] = useState<Scope>(
    searchParams.get('scope') === 'assigned' ? 'assigned' : 'mine',
  );
  const [data, setData] = useState<ApprovalListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ApprovalListResponse>(`/approvals?scope=${scope}`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof ApiError ? caught.message : '결재 목록을 불러오지 못했습니다.');
      });
    return () => controller.abort();
  }, [scope, attempt]);

  const changeScope = (nextScope: Scope) => {
    if (nextScope === scope) return;
    setScope(nextScope);
    setData(null);
    setError(null);
  };

  return (
    <AppShell>
      <header className="page-header">
        <div>
          <p className="eyebrow">APPROVAL WORKSPACE</p>
          <h1>전자결재</h1>
          <p>내가 작성한 문서와 결재가 필요한 문서를 분리해 확인합니다.</p>
        </div>
        <div className="page-header-actions">
          <Link
            className={configuration?.enabled ? 'primary-button' : 'secondary-button'}
            href="/approvals/new"
          >
            직접 작성
          </Link>
          {configuration && !configuration.enabled && (
            <Link className="primary-button" href="/approvals/ai-draft">
              AI로 초안 만들기
            </Link>
          )}
        </div>
      </header>

      <div className="segmented-control" role="tablist" aria-label="결재 목록 범위">
        <button aria-selected={scope === 'mine'} onClick={() => changeScope('mine')} role="tab">
          내가 작성한 문서
        </button>
        <button
          aria-selected={scope === 'assigned'}
          onClick={() => changeScope('assigned')}
          role="tab"
        >
          내가 결재할 문서
        </button>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}{' '}
          <button
            className="text-button"
            onClick={() => {
              setError(null);
              setAttempt((value) => value + 1);
            }}
          >
            다시 시도
          </button>
        </div>
      )}
      {!data && !error && <div className="empty-card">결재 문서를 불러오는 중입니다.</div>}
      {data?.total === 0 && (
        <div className="empty-card">
          <strong>
            {scope === 'mine' ? '작성한 결재가 없습니다.' : '배정된 결재가 없습니다.'}
          </strong>
          <span>
            {scope === 'mine'
              ? '첫 초안을 작성해 업무 흐름을 시작해보세요.'
              : '새 요청이 오면 이곳에 표시됩니다.'}
          </span>
        </div>
      )}
      {data && data.total > 0 && (
        <div className="approval-list">
          {data.items.map((approval) => (
            <Link className="approval-row" href={`/approvals/${approval.id}`} key={approval.id}>
              <div>
                <div className="row-meta">
                  <span>{approvalTypeLabels[approval.type]}</span>
                  <span>·</span>
                  <span>{formatDate(approval.updatedAt)}</span>
                </div>
                <h2>{approval.title}</h2>
                <p>{approval.content || '내용이 아직 작성되지 않았습니다.'}</p>
              </div>
              <div className="row-end">
                <StatusBadge status={approval.status} />
                <strong>
                  {approval.details.kind === 'LEAVE'
                    ? `${approval.details.requestedDays ?? '-'}일`
                    : formatCurrency(approval.amount)}
                </strong>
                <span>
                  {scope === 'mine'
                    ? `결재선 ${approval.lines.length}건`
                    : `작성자 ${approval.author.name}`}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}

export default function ApprovalListPage() {
  return (
    <Suspense fallback={<main className="centered-state">결재 목록을 준비하고 있습니다.</main>}>
      <ApprovalListContent />
    </Suspense>
  );
}
