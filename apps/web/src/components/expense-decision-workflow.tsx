'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { ApiError, apiFetch, getUserErrorMessage } from '@/lib/api';
import { formatCurrency } from '@/lib/format';
import type { Approval, ApprovalDraftPrepareResponse } from '@/lib/types';
import { ExpenseVerification } from '@/components/expense-verification';

type Policy = NonNullable<ApprovalDraftPrepareResponse['policyValidation']>;
interface Revision {
  approvalId: string;
  version: number;
  rejectionComment: string;
  prepared: ApprovalDraftPrepareResponse;
  changes: { field: string; before: string | number | null; after: string | number | null }[];
  applyToken: string | null;
}
interface Brief {
  approvalId: string;
  version: number;
  checks: { missingFields: string[]; duplicateMatches: { id: string; title: string }[]; moreMatches: boolean };
  policy: Policy;
  rejectionComment: string | null;
  receiptReference: string | null;
}
const labels: Record<string, string> = {
  title: '제목', content: '업무 내용', amount: '금액', 'details.expenseDate': '지출일',
  'details.merchant': '사용처', 'details.category': '비용 구분', 'details.purpose': '업무 목적',
  'details.receiptReference': '증빙 참조',
};
const panel = 'tw:my-5 tw:rounded-lg tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-5';

export function ExpenseRevisionPanel({ approval, onUpdated }: { approval: Approval; onUpdated: (value: Approval) => void }) {
  const { configuration } = useDemoConfiguration();
  const [answer, setAnswer] = useState('');
  const [answers, setAnswers] = useState<string[]>([]);
  const [result, setResult] = useState<Revision | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  if (configuration?.enabled || !configuration?.aiCapabilities?.approvalDraft) {
    return <section className={panel} aria-label="반려 경비 보완 안내">
      <h2>반려 의견을 반영해 보완하세요</h2>
      <p>이 환경에서는 AI 수정 제안을 제공하지 않습니다. 아래 ‘다시 수정하기’로 초안을 열어 반려 의견을 확인하며 직접 수정할 수 있습니다.</p>
    </section>;
  }
  async function prepare() {
    if (inFlight.current || stale) return;
    inFlight.current = true; setBusy(true); setError(null); setResult(null);
    const next = answer.trim() ? [...answers, answer.trim()] : answers;
    try {
      const value = await apiFetch<Revision>(`/approvals/${approval.id}/expense-revision/prepare`, {
        method: 'POST', body: JSON.stringify({ version: approval.version, answers: next }),
      });
      setResult(value); setAnswers(next); setAnswer('');
    } catch (caught) {
      setError(getUserErrorMessage(caught, '수정 제안을 준비하지 못했습니다. 입력을 유지했으니 다시 시도하거나 직접 수정해 주세요.'));
      if (caught instanceof ApiError && ['VERSION_CONFLICT', 'INVALID_STATUS'].includes(caught.code)) setStale(true);
    } finally { setBusy(false); inFlight.current = false; }
  }
  async function apply() {
    if (!result?.applyToken || !result.prepared.preview || inFlight.current || stale) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const updated = await apiFetch<Approval>(`/approvals/${approval.id}/expense-revision/apply`, {
        method: 'POST', body: JSON.stringify({ version: result.version, preview: result.prepared.preview, applyToken: result.applyToken }),
      });
      onUpdated(updated);
    } catch (caught) {
      setError(getUserErrorMessage(caught, '반영 결과를 확인하지 못했습니다. 문서를 새로고침해 저장 여부를 확인해 주세요.'));
      setResult(null); // No automatic retry of a possibly successful write.
      setStale(true);
    } finally { setBusy(false); inFlight.current = false; }
  }
  return <section className={panel} aria-label="반려 경비 AI 수정 제안">
    <h2 className="tw:mt-0">반려 의견에서 수정까지</h2>
    <p>반려 의견은 수정 요청으로 전달합니다. 새로운 지출 사실은 작성자가 알려준 내용만 사용하며, 제안 준비만으로 문서는 바뀌지 않습니다.</p>
    {error && <p role="alert" className="error-banner">{error}</p>}
    {stale && <p>문서를 새로고침해 최신 상태를 확인해 주세요. 작성한 추가 사실은 복사해 보관할 수 있습니다.</p>}
    {result && <>
      {result.prepared.provider === 'fake' && <p role="note">시뮬레이션 응답 · 로컬 화면 검증용이며 실제 AI 모델을 호출하지 않습니다.</p>}
      <details><summary>제안에 사용한 반려 의견</summary><blockquote className="tw:mx-0 tw:whitespace-pre-wrap">{result.rejectionComment}</blockquote></details>
      <details className="tw:my-4"><summary>필드·규정 검사 상세 보기</summary><ExpenseVerification result={result.prepared} /></details>
      {result.prepared.questions.length > 0 && <ul>{result.prepared.questions.map((q) => <li key={q.field}>{q.prompt}</li>)}</ul>}
      {result.prepared.status === 'UNSUPPORTED' && <p>{result.prepared.assistantMessage}</p>}
      {result.prepared.preview && <>
        <h3>변경 전후를 확인하세요</h3>
        <p>변경되지 않는 항목은 유지됩니다. 이 제안이 모든 반려 사유를 해결했다는 뜻은 아닙니다.</p>
        <div className="tw:grid tw:gap-3">{result.changes.map((change) => <div key={change.field} className="tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:pl-3">
          <strong>{labels[change.field] ?? change.field}</strong>
          <dl className="tw:my-2 tw:grid tw:gap-2 tw:sm:grid-cols-2">
            <div><dt className="tw:text-jhw-muted">변경 전</dt><dd className="tw:m-0 tw:whitespace-pre-wrap tw:break-words">{change.before ?? '미입력'}</dd></div>
            <div><dt className="tw:text-jhw-muted">제안</dt><dd className="tw:m-0 tw:whitespace-pre-wrap tw:break-words">{change.after ?? '미입력'}</dd></div>
          </dl>
        </div>)}</div>
        {result.changes.length === 0 && <p>필드 변경 제안이 없습니다. 반려 의견에 필요한 사실을 추가하거나 직접 수정해 주세요.</p>}
        <button className="primary-button" type="button" disabled={busy || stale || !result.applyToken} onClick={apply}>변경 확인 후 같은 문서의 초안에 반영</button>
        <p className="tw:text-sm tw:text-jhw-muted">반려 이력을 유지하고 초안으로 전환합니다. 제출·승인은 실행하지 않습니다.</p>
      </>}
    </>}
    <label className="tw:my-4 tw:grid tw:gap-2">보완할 실제 사실
      <textarea rows={3} value={answer} disabled={busy} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} placeholder="예: 목적: CES 협력사 데모 시연; 증빙 참조: RCP-CES-002" />
    </label>
    {answers.length > 0 && <details><summary>이전에 제공한 추가 사실 {answers.length}개</summary>{answers.map((text, index) => <p key={index} className="tw:whitespace-pre-wrap tw:break-words">{text}</p>)}</details>}
    <button className="secondary-button" type="button" disabled={busy || stale || answers.length >= 8} onClick={prepare}>{busy ? '처리 중…' : result ? '추가 사실로 제안 다시 준비' : '반려 의견으로 AI 수정 제안 준비'}</button>
  </section>;
}

export function ExpenseDecisionPanel({ approval }: { approval: Approval }) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Brief>(`/approvals/${approval.id}/decision-brief?version=${approval.version}`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) {
        if (value.version !== approval.version) { setError('문서가 변경됐습니다. 새로고침해 주세요.'); return; }
        setBrief(value); setError(null);
      } }).catch((caught) => { if (!controller.signal.aborted) setError(getUserErrorMessage(caught, '검토 근거를 불러오지 못했습니다. 문서와 규정을 직접 확인하거나 다시 조회해 주세요.')); });
    return () => controller.abort();
  }, [approval.id, approval.version, attempt]);
  return <section className={panel} aria-label="결재자 경비 검토 요약">
    <h2 className="tw:mt-0">결정 전에 확인할 경비</h2>
    <p className="tw:text-sm tw:text-jhw-muted">문서 v{approval.version} 기준 · 서버 규칙과 현재 규정 원문을 모았습니다. AI 승인 추천이나 규정 전체 준수 판정은 아닙니다.</p>
    <p><strong>{formatCurrency(approval.amount)}</strong> · {approval.details.kind === 'EXPENSE' ? approval.details.merchant : ''}</p>
    {error ? <div role="alert"><p>{error}</p><button type="button" className="text-button" onClick={() => { setBrief(null); setError(null); setAttempt((n) => n + 1); }}>검토 근거 다시 조회</button></div> : !brief ? <p role="status">검토 근거를 확인하고 있습니다.</p> : <>
      <div className="tw:grid tw:gap-6 tw:lg:grid-cols-2"><div><h3>필수 정보와 중복 후보</h3>
      <p>{brief.checks.missingFields.length ? '보완할 필수 항목이 있습니다.' : '필수 지출 정보가 입력됐습니다.'}</p>
      {brief.checks.missingFields.map((field) => <p key={field}>{labels[field] ?? field}</p>)}
      {brief.checks.duplicateMatches.length ? <ul>{brief.checks.duplicateMatches.map((item) => <li key={item.id}><Link href={`/approvals/${item.id}`}>{item.title}</Link></li>)}</ul> : <p>조회 가능한 문서에서 같은 지출일·사용처·금액의 후보를 찾지 못했습니다.</p>}
      <p className="tw:text-sm tw:text-jhw-muted">중복 후보는 실제 중복 지출의 증명이 아닙니다.{brief.checks.moreMatches && ' 최근 후보 3건만 표시합니다.'}</p>
      </div><div><h3>규정 기준과 증빙</h3>
      <p>증빙 참조: {brief.receiptReference ?? '미입력'} · 원본 첨부·진위는 확인되지 않았습니다.</p>
      {brief.policy.status === 'UNAVAILABLE' && <p>활성 규정을 조회하지 못했습니다. 규정 준수 여부는 확인되지 않았습니다.</p>}
      <ul className="tw:list-none tw:p-0">{[...brief.policy.checks].sort((a, b) => Number(b.outcome === 'ACTION_REQUIRED') - Number(a.outcome === 'ACTION_REQUIRED')).map((check) => {
        const source = brief.policy.citations.find((c) => c.citationKey === check.citationKey);
        return <li key={check.citationKey} className="tw:my-4 tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:pl-3">
          <strong>{check.outcome === 'ACTION_REQUIRED' ? '추가 확인 필요' : check.outcome === 'NOT_APPLICABLE' ? '이 기준의 대상 아님' : '자동 판정하지 않음'}</strong>
          <p>{check.message}</p>
          {source && <details><summary>근거: {source.sectionTitle} · {source.version}</summary><p>{source.excerpt}</p><Link href="/policies">규정 전체 보기</Link></details>}
        </li>;
      })}</ul></div></div>
      {brief.rejectionComment && <><h3>이전 회차의 반려 의견</h3><blockquote className="tw:mx-0 tw:whitespace-pre-wrap tw:break-words">{brief.rejectionComment}</blockquote><p>보완 완료 여부는 아래 현재 문서와 비교해 확인해 주세요. 과거 문서 snapshot과의 자동 비교는 제공하지 않습니다.</p></>}
    </>}
  </section>;
}
