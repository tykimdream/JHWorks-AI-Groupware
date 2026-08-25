'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { AppShell } from '@/components/app-shell';
import { StatusBadge } from '@/components/status-badge';
import { ApiError, apiFetch } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/format';
import type { ApprovalListResponse } from '@/lib/types';

type Scope = 'mine' | 'assigned';

export default function ApprovalListPage() {
  const [scope, setScope] = useState<Scope>('mine');
  const [data, setData] = useState<ApprovalListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ApprovalListResponse>(`/approvals?scope=${scope}`)
      .then(setData)
      .catch((caught: unknown) => {
        setError(caught instanceof ApiError ? caught.message : '결재 목록을 불러오지 못했습니다.');
      });
  }, [scope]);

  const changeScope = (nextScope: Scope) => {
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
        <Link className="primary-button" href="/approvals/new">
          새 결재 작성
        </Link>
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

      {error && <p className="error-banner">{error}</p>}
      {!data && !error && <div className="empty-card">결재 문서를 불러오는 중입니다.</div>}
      {data?.total === 0 && (
        <div className="empty-card">
          <strong>{scope === 'mine' ? '작성한 결재가 없습니다.' : '배정된 결재가 없습니다.'}</strong>
          <span>{scope === 'mine' ? '첫 Draft를 작성해 업무 흐름을 시작해보세요.' : '새 요청이 오면 이곳에 표시됩니다.'}</span>
        </div>
      )}
      {data && data.total > 0 && (
        <div className="approval-list">
          {data.items.map((approval) => (
            <Link className="approval-row" href={`/approvals/${approval.id}`} key={approval.id}>
              <div>
                <div className="row-meta">
                  <span>{approval.type === 'BUSINESS_TRIP' ? '출장 신청' : '일반 결재'}</span>
                  <span>·</span>
                  <span>{formatDate(approval.updatedAt)}</span>
                </div>
                <h2>{approval.title}</h2>
                <p>{approval.content || '내용이 아직 작성되지 않았습니다.'}</p>
              </div>
              <div className="row-end">
                <StatusBadge status={approval.status} />
                <strong>{formatCurrency(approval.amount)}</strong>
                <span>{scope === 'mine' ? `결재선 ${approval.lines.length}건` : `작성자 ${approval.author.name}`}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
