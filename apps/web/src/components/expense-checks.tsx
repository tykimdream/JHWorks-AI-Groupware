'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { WorkspaceIcon } from '@/components/workspace-icon';
import { StatusBadge } from '@/components/status-badge';
import type { ApprovalStatus } from '@/lib/types';

interface ExpenseChecks {
  approvalId: string;
  approvalTitle: string;
  version: number;
  missingFields: string[];
  duplicateMatches: { id: string; title: string; status: ApprovalStatus }[];
  moreMatches: boolean;
  checkedAt: string;
}

interface ExpenseInsights {
  items: ExpenseChecks[];
  checkedCount: number;
  hasMoreDocuments: boolean;
  checkedAt: string;
}

const fieldLabels: Record<string, string> = {
  'details.expenseDate': '실제 지출일(미래 날짜 불가)',
  'details.merchant': '사용처',
  'details.category': '비용 구분',
  'details.purpose': '업무 목적',
  amount: '0원보다 큰 실제 지출 금액',
};

function Findings({ checks }: { checks: ExpenseChecks }) {
  return (
    <>
      {checks.missingFields.length > 0 && (
        <p className="expense-finding">
          <strong>제출 전에 보완해 주세요</strong>
          <span>
            {checks.missingFields.map((field) => fieldLabels[field] ?? field).join(' · ')}
          </span>
        </p>
      )}
      {checks.duplicateMatches.length > 0 && (
        <div className="expense-finding">
          <strong>같은 지출이 이미 등록됐을 수 있어요</strong>
          <p>
            같은 작성자의 지출일·사용처·금액이 일치합니다. 별도 지출일 수도 있으니 원본을 비교해
            주세요.
          </p>
          <ul>
            {checks.duplicateMatches.map((match) => (
              <li key={match.id}>
                <Link href={`/approvals/${match.id}`}>
                  {match.title}
                  <span aria-hidden="true"> ↗</span>
                </Link>
                <StatusBadge status={match.status} />
              </li>
            ))}
          </ul>
          {checks.moreMatches && <span>일치 문서는 최근 3건만 표시합니다.</span>}
        </div>
      )}
    </>
  );
}

export function ExpenseChecksPanel({
  approvalId,
  version,
  status = 'DRAFT',
}: {
  approvalId: string;
  version: number;
  status?: ApprovalStatus;
}) {
  const [checks, setChecks] = useState<ExpenseChecks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ExpenseChecks>(`/approvals/${approvalId}/expense-checks`, {
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.version !== version) {
          setError('문서가 변경됐습니다. 페이지를 새로고침해 최신 내용을 확인해 주세요.');
          return;
        }
        setChecks(result);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(getUserErrorMessage(caught, '경비 확인 정보를 불러오지 못했습니다.'));
      });
    return () => controller.abort();
  }, [approvalId, version, attempt]);
  return (
    <section className="expense-check-panel" aria-label="경비 사전 확인">
      <div className="expense-check-heading">
        <WorkspaceIcon name="search" size={18} />
        <h2>{status === 'DRAFT' ? '제출 전에 한 번 더 확인하세요' : '경비 확인 결과'}</h2>
        <span className="small-pill">문서 데이터 기준</span>
      </div>
      {error ? (
        <div role="alert">
          <p>{error}</p>
          <button
            className="text-button"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            다시 확인
          </button>
        </div>
      ) : !checks ? (
        <p role="status">누락 정보와 중복 가능성을 확인하고 있습니다.</p>
      ) : (
        <>
          <Findings checks={checks} />
          {!checks.missingFields.length && !checks.duplicateMatches.length && (
            <p>
              필수 지출 정보가 입력됐고, 조회 가능한 문서에서 같은 지출일·사용처·금액의 경비를 찾지
              못했습니다. 영수증 원본과 다른 중복 가능성은 별도로 확인해 주세요.
            </p>
          )}
        </>
      )}
    </section>
  );
}

export function ExpenseInsightPanel() {
  const [insights, setInsights] = useState<ExpenseInsights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<ExpenseInsights>('/approvals/expense-insights', { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) {
          setInsights(result);
          setError(null);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(getUserErrorMessage(caught, '경비 제안을 불러오지 못했습니다.'));
      });
    return () => controller.abort();
  }, [attempt]);
  return (
    <section className="home-panel expense-insight-panel" aria-label="미리 확인할 경비">
      <div className="panel-heading">
        <h2>
          <WorkspaceIcon name="search" size={17} />
          미리 확인할 경비
        </h2>
        <span className="small-pill">최근 경비 10개 기준</span>
      </div>
      {error ? (
        <div className="expense-insight-body" role="alert">
          <p>{error}</p>
          <button
            className="text-button"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            다시 확인
          </button>
        </div>
      ) : !insights ? (
        <p className="expense-insight-body" role="status">
          내 경비 문서를 확인하고 있습니다.
        </p>
      ) : (
        <div className="expense-insight-body">
          {insights.items.length === 0 ? (
            <p>
              {insights.checkedCount === 0
                ? '확인할 경비 초안이나 결재 중인 정산이 없습니다.'
                : `최근 확인한 경비 ${insights.checkedCount}개에서 필수 정보 누락이나 같은 지출의 중복 가능성을 찾지 못했습니다.`}
            </p>
          ) : (
            insights.items.slice(0, 3).map((item) => (
              <article key={item.approvalId}>
                <Link className="expense-insight-title" href={`/approvals/${item.approvalId}`}>
                  {item.approvalTitle}
                  <WorkspaceIcon name="arrow" size={15} />
                </Link>
                <Findings checks={item} />
              </article>
            ))
          )}
          {(insights.hasMoreDocuments || insights.items.length > 3) && (
            <Link href="/approvals">추가 경비는 전자결재 목록에서 확인해 주세요 →</Link>
          )}
          <p className="expense-check-caption">
            조회 가능한 내 초안·결재 중인 경비를 최근 수정 순으로 점검합니다. 제안만으로 문서를
            변경하거나 제출하지 않습니다.
          </p>
        </div>
      )}
    </section>
  );
}
