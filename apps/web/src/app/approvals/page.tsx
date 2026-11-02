'use client';

import Link from 'next/link';
import { EmptyState, Select } from '@jhworks/pattern/react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';

import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { AppShell } from '@/components/app-shell';
import { StatusBadge } from '@/components/status-badge';
import { ApiError, apiFetch } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/format';
import type { ApprovalStatus, ApprovalSummaryPage } from '@/lib/types';
import { approvalTypeLabels } from '@/lib/approval-labels';

type Scope = 'mine' | 'assigned';
const pageSize = 20;
const statuses: ApprovalStatus[] = ['DRAFT', 'PENDING', 'APPROVED', 'REJECTED'];

function ApprovalListRoute() {
  const searchParams = useSearchParams();
  const scope: Scope = searchParams.get('scope') === 'assigned' ? 'assigned' : 'mine';
  const rawPage = searchParams.get('page');
  const page = rawPage && /^\d+$/.test(rawPage) ? Math.min(501, Math.max(1, Number(rawPage))) : 1;
  const rawStatus = searchParams.get('status');
  const status = statuses.find((value) => value === rawStatus) ?? null;
  return <ApprovalListContent scope={scope} page={page} status={status} />;
}

function ApprovalListContent({ scope, page, status }: { scope: Scope; page: number; status: ApprovalStatus | null }) {
  const router = useRouter();
  const { configuration } = useDemoConfiguration();
  const restoredRow = useRef<string | null>(null);
  const requestKey = `${scope}:${page}:${status ?? ''}`;
  const [result, setResult] = useState<{
    key: string;
    data: ApprovalSummaryPage | null;
    error: string | null;
  } | null>(null);
  const data = result?.key === requestKey ? result.data : null;
  const error = result?.key === requestKey ? result.error : null;
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ scope, limit: String(pageSize), offset: String((page - 1) * pageSize) });
    if (status) params.set('status', status);
    apiFetch<ApprovalSummaryPage>(`/approvals/summaries?${params}`, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key: requestKey, data, error: null });
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setResult({ key: requestKey, data: null, error: caught instanceof ApiError ? caught.message : '결재 목록을 불러오지 못했습니다.' });
      });
    return () => controller.abort();
  }, [scope, page, status, requestKey, attempt]);

  const listUrl = (nextScope: Scope, nextPage: number, nextStatus: ApprovalStatus | null) => {
    const params = new URLSearchParams({ scope: nextScope });
    if (nextPage > 1) params.set('page', String(nextPage));
    if (nextStatus) params.set('status', nextStatus);
    return `/approvals?${params}`;
  };
  const changeScope = (nextScope: Scope) => {
    if (nextScope === scope) return;
    router.push(listUrl(nextScope, 1, null), { scroll: false });
  };

  return (
    <AppShell>
      <header className="page-header">
        <div>
          <p className="eyebrow">APPROVAL WORKSPACE</p>
          <h1>전자결재</h1>
          <p>내가 작성한 문서와 배정된 결재 문서를 분리해 확인합니다.</p>
        </div>
        <div className="page-header-actions">
          <Link
            className={configuration?.aiCapabilities?.approvalDraft ? 'secondary-button' : 'primary-button'}
            href="/approvals/new"
          >
            직접 작성
          </Link>
          {configuration?.aiCapabilities?.approvalDraft && (
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
          내게 배정된 문서
        </button>
      </div>

      <label className="tw:mt-4 tw:flex tw:items-center tw:gap-2">
        <span>상태</span>
        <Select className="tw:max-w-44" value={status ?? ''} onChange={(event) => router.push(listUrl(scope, 1, statuses.find((value) => value === event.target.value) ?? null), { scroll: false })}>
          <option value="">전체</option><option value="DRAFT">초안</option><option value="PENDING">결재 대기</option><option value="APPROVED">승인</option><option value="REJECTED">반려</option>
        </Select>
      </label>

      {error && (
        <div className="error-banner" role="alert">
          {error}{' '}
          <button
            className="text-button"
            onClick={() => {
              setResult(null);
              setAttempt((value) => value + 1);
            }}
          >
            다시 시도
          </button>
        </div>
      )}
      {!data && !error && <div className="empty-card">결재 문서를 불러오는 중입니다.</div>}
      {data?.total === 0 && page === 1 && (
        <EmptyState
          title={status ? '해당 상태의 문서가 없습니다.' : scope === 'mine' ? '작성한 결재가 없습니다.' : '배정된 결재가 없습니다.'}
          description={status ? '다른 상태를 선택해 확인해 주세요.' : scope === 'mine' ? '첫 초안을 작성해 업무 흐름을 시작해보세요.' : '새 요청이 오면 이곳에 표시됩니다.'}
        />
      )}
      {data && data.total > 0 && (
        <div className="approval-list">
          {data.items.map((approval) => (
            <Link
              className="approval-row tw:scroll-mt-6 tw:focus-visible:outline-2 tw:focus-visible:outline-offset-4 tw:focus-visible:outline-jhw-primary"
              id={`approval-${approval.id}`}
              href={`/approvals/${approval.id}?from=${scope}${page > 1 ? `&fromPage=${page}` : ''}${status ? `&fromStatus=${status}` : ''}`}
              key={approval.id}
              ref={(node) => {
                const target = `#${encodeURIComponent(`approval-${approval.id}`)}`;
                if (!node || window.location.hash !== target || restoredRow.current === target) return;
                restoredRow.current = target;
                node.focus({ preventScroll: true });
                node.scrollIntoView({ block: 'center', behavior: 'instant' });
              }}
            >
              <div>
                <div className="row-meta">
                  <span>{approvalTypeLabels[approval.type]}</span>
                  <span>·</span>
                  <span>{formatDate(approval.updatedAt)}</span>
                </div>
                <h2>{approval.title}</h2>
                <p>{approval.contentPreview || '내용이 아직 작성되지 않았습니다.'}</p>
              </div>
              <div className="row-end">
                <StatusBadge status={approval.status} />
                <strong>
                  {approval.type === 'LEAVE'
                    ? `${approval.leaveDays ?? '-'}일`
                    : formatCurrency(approval.amount)}
                </strong>
                <span>
                  {scope === 'mine'
                    ? `결재선 ${approval.lineCount}건`
                    : `작성자 ${approval.author.name}`}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
      {data && (data.total > 0 || page > 1) && <nav aria-label="결재 목록 페이지" className="button-row tw:mt-5">
        {page > 1 && <Link className="secondary-button" href={listUrl(scope, page - 1, status)}>이전</Link>}
        <span>{page}페이지 · 총 {data.total}건</span>
        {page * pageSize < data.total && page < 501 && <Link className="secondary-button" href={listUrl(scope, page + 1, status)}>다음</Link>}
      </nav>}
      {data && page === 501 && page * pageSize < data.total && <p role="status">현재 조건에서는 최대 10,020건까지만 볼 수 있습니다. 상태를 바꾸면 다른 문서를 볼 수 있습니다.</p>}
      {data && page > 1 && data.items.length === 0 && <p role="status">이 페이지에 문서가 없습니다. 이전 페이지를 확인해 주세요.</p>}
    </AppShell>
  );
}

export default function ApprovalListPage() {
  return (
    <Suspense fallback={<main className="centered-state">결재 목록을 준비하고 있습니다.</main>}>
      <ApprovalListRoute />
    </Suspense>
  );
}
