'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

import { ApiError, apiFetch, getUserErrorMessage } from '@/lib/api';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { formatCurrency } from '@/lib/format';
import { approvalTypeLabels } from '@/lib/approval-labels';
import { ExpenseVerification } from '@/components/expense-verification';
import { ExpenseSummary } from '@/components/expense-summary';
import { useWorkspaceEmployee } from '@/components/app-shell';
import { readDraftRequest, clearDraftRequest } from '@/lib/draft-handoff';
import { storeManualDraft } from '@/lib/manual-draft-handoff';
import type { Approval, ApprovalDraftPrepareResponse, BusinessTripDetails } from '@/lib/types';

const starterExamples = [
  'CES 2026에서 햄버거 30,000원 먹은 거 올려줘.',
  '다음 주 화요일 부산에서 열리는 CES 협력사 미팅 출장 신청을 준비해줘. 예상 교통비는 17만원이야.',
  '신규 파트너 온보딩을 위한 일반 업무 협조 결재 초안 작성해줘.',
];

const policyStatusLabels = {
  READY: '관련 출장 규정을 찾았습니다.',
  NOT_APPLICABLE: '이 문서 유형에는 검색할 정책이 없습니다.',
  NOT_INDEXED: '정책 인덱스가 준비되지 않았습니다.',
  UNAVAILABLE: '정책 검색을 사용할 수 없습니다.',
};

export const ApprovalDraftAssistant = () => {
  const router = useRouter();
  const { configuration } = useDemoConfiguration();
  const expenseOnly = configuration?.enabled === true;
  const employee = useWorkspaceEmployee();
  const [request, setRequest] = useState(() => (employee ? readDraftRequest(employee.id) : ''));
  useEffect(() => {
    if (employee) clearDraftRequest(employee.id);
  }, [employee]);
  const [answers, setAnswers] = useState<string[]>([]);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<ApprovalDraftPrepareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [handoffError, setHandoffError] = useState<string | null>(null);
  const continueManually = () => {
    const content = [request, ...answers, answer].filter((text) => text.trim()).join('\n\n');
    if (!employee || !storeManualDraft(employee.id, {
      content,
      type: expenseOnly ? 'EXPENSE' : result?.preview?.type,
    })) {
      setHandoffError('입력을 옮기지 못했습니다. 브라우저 저장 권한과 전체 5,000자 한도를 확인해주세요. 현재 입력은 유지됩니다.');
      return;
    }
    router.push('/approvals/new?handoff=manual');
  };

  const prepare = async (nextAnswers: string[]) => {
    setHandoffError(null);
    setError(null);
    setIsPreparing(true);
    try {
      const prepared = await apiFetch<ApprovalDraftPrepareResponse>(
        '/approval-draft-assistant/prepare',
        {
          method: 'POST',
          body: JSON.stringify({ request, answers: nextAnswers }),
        },
      );
      setAnswers(nextAnswers);
      setResult(prepared);
      setAnswer('');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, 'AI 초안을 준비하지 못했습니다.'));
    } finally {
      setIsPreparing(false);
    }
  };

  const handleInitialRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!request.trim()) return;
    await prepare(answers);
  };

  const handleFollowUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = answer.trim();
    if (!trimmed) return;
    await prepare([...answers, trimmed]);
  };

  const expenseVerified = result?.preview?.type !== 'EXPENSE' || (
    result.grounding?.status === 'INPUT_MATCHED'
    && result.execution?.outcome === 'PREVIEW'
    && Boolean(result.policyValidation?.fingerprint)
  );
  const handleConfirm = async () => {
    if (!result?.preview || !result.confirmationToken || !expenseVerified) return;
    setError(null);
    setIsConfirming(true);
    try {
      const approval = await apiFetch<Approval>('/approval-draft-assistant/confirm', {
        method: 'POST',
        body: JSON.stringify({
          preview: result.preview,
          confirmationToken: result.confirmationToken,
        }),
      });
      router.push(`/approvals/${approval.id}/edit`);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '초안을 저장하지 못했습니다.'));
      if (caught instanceof ApiError && caught.code === 'POLICY_CHANGED') setResult(null);
    } finally {
      setIsConfirming(false);
    }
  };

  const reset = () => {
    setHandoffError(null);
    setRequest('');
    setAnswers([]);
    setAnswer('');
    setResult(null);
    setError(null);
  };

  const previewTrip =
    result?.preview?.details.kind === 'BUSINESS_TRIP'
      ? (result.preview.details as BusinessTripDetails)
      : null;

  return (
    <div className="draft-studio">
      <p className="draft-support-note">
        {expenseOnly
          ? '경비 입력을 원문과 대조하고 활성 규정의 지원 기준을 검사합니다. 영수증 원본 검증·규정 전체 판정은 제공하지 않습니다.'
          : '출장·경비·일반 초안을 준비합니다. 경비는 필드·규정 검사 결과를 확인할 수 있으며, 저장과 제출은 별도입니다.'}
      </p>
      <div className="draft-progress" aria-label="초안 작성 단계">
        <span className={!result ? 'current' : ''}>
          01 <strong>업무 요청</strong>
        </span>
        <i />
        <span className={result?.status === 'NEEDS_INPUT' ? 'current' : ''}>
          02 <strong>정보 확인</strong>
        </span>
        <i />
        <span className={result?.preview ? 'current' : ''}>
          03 <strong>검토 후 저장</strong>
        </span>
      </div>
      <div className="draft-assistant-layout">
        <section className="draft-conversation-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">JHWORKS AI</p>
              <h2>{expenseOnly ? '어떤 비용을 사용하셨나요?' : '어떤 결재가 필요한가요?'}</h2>
            </div>
            {result && (
              <button className="text-button" onClick={reset} type="button">
                처음부터 다시
              </button>
            )}
          </div>

          {!result && (
            <>
              <form className="draft-request-form" onSubmit={handleInitialRequest}>
                <label>
                  <span>업무 요청</span>
                  <textarea
                    disabled={isPreparing}
                    maxLength={2000}
                    onChange={(event) => setRequest(event.target.value)}
                    placeholder={expenseOnly
                      ? '예: 이번 CES 출장에서 쓴 17만원 경비 정산 결재를 준비해줘.'
                      : '예: 다음 주 화요일 부산 고객사 미팅 출장 결재 만들어줘.'}
                    rows={5}
                    value={request}
                  />
                </label>
                <button
                  className="ai-button"
                  disabled={isPreparing || !request.trim()}
                  type="submit"
                >
                  {isPreparing ? '내용 파악 중…' : 'AI로 초안 준비'}
                </button>
              </form>
              <div className="draft-examples">
                <span>예시로 시작하기</span>
                {(expenseOnly ? starterExamples.slice(0, 1) : starterExamples).map((example) => (
                  <button
                    key={example}
                    disabled={isPreparing}
                    onClick={() => setRequest(example)}
                    type="button"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </>
          )}

          {result && (
            <div className="draft-conversation">
              {result.provider === 'fake' && (
                <p className="simulation-notice" role="status">
                  시뮬레이션 응답 · 로컬 화면 검증용이며 실제 AI 모델을 호출하지 않습니다.
                </p>
              )}
              <div className="conversation-message user-message">
                <span>나</span>
                <p>{request}</p>
              </div>
              {answers.map((item, index) => (
                <div className="conversation-message user-message" key={`${item}-${index}`}>
                  <span>추가 답변 {index + 1}</span>
                  <p>{item}</p>
                </div>
              ))}
              <div className="conversation-message assistant-message">
                <span>JHWorks AI</span>
                <p>{result.assistantMessage}</p>
                {result.questions.length > 0 && (
                  <ul>
                    {result.questions.map((question) => (
                      <li key={question.field}>{question.prompt}</li>
                    ))}
                  </ul>
                )}
              </div>

              <ExpenseVerification result={result} />

              {result.status === 'NEEDS_INPUT' && (
                <form className="draft-follow-up-form" onSubmit={handleFollowUp}>
                  <label>
                    <span>추가 정보</span>
                    <textarea
                      maxLength={2000}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="질문에 한 문장으로 함께 답해도 됩니다."
                      rows={4}
                      value={answer}
                    />
                  </label>
                  <button
                    className="ai-button"
                    disabled={isPreparing || !answer.trim()}
                    type="submit"
                  >
                    {isPreparing ? '초안 갱신 중…' : '답변 반영'}
                  </button>
                </form>
              )}

              {result.status === 'UNSUPPORTED' && (
                <div className="unsupported-actions">
                  <button className="secondary-button" type="button" onClick={continueManually}>
                    수동으로 작성
                  </button>
                </div>
              )}
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <p>{error}</p>
              <button type="button" className="text-button" onClick={continueManually}>
                직접 작성으로 계속 →
              </button>
            </div>
          )}
          {handoffError && <p role="alert" className="error-banner">{handoffError}</p>}
        </section>

        <aside className="draft-preview-column">
          {!result?.preview && (
            <div className="draft-placeholder">
              <span className="preview-paper-icon">↗</span>
              <p className="eyebrow">LIVE PREVIEW</p>
              <strong>
                말로 시작해서,
                <br />
                문서로 완성하세요.
              </strong>
              <p>
                요청을 입력하면 필요한 정보를 확인하고
                <br />
                회사 양식에 맞는 초안을 이곳에 준비합니다.
              </p>
              <div className="preview-paper-lines" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
              <div className="preview-safety-note">
                직접 확인하기 전에는 저장하거나 제출하지 않습니다.
              </div>
            </div>
          )}

          {result?.preview && (
            <>
              <section className="draft-preview-card">
                <div className="preview-state">
                  <span>저장 전 미리보기</span>
                  <strong>{approvalTypeLabels[result.preview.type]}</strong>
                </div>
                <h2>{result.preview.title}</h2>
                <p className="preview-content">{result.preview.content}</p>
                {result.preview.details.kind === 'EXPENSE' && (
                  <ExpenseSummary expense={result.preview.details} amount={result.preview.amount} />
                )}
                {result.preview.type !== 'EXPENSE' && (
                  <dl className="preview-detail-grid">
                    {previewTrip && (
                      <>
                        <div>
                          <dt>출장지</dt>
                          <dd>{previewTrip.destination}</dd>
                        </div>
                        <div>
                          <dt>관계처/행사</dt>
                          <dd>{previewTrip.clientName}</dd>
                        </div>
                        <div>
                          <dt>기간</dt>
                          <dd>{`${previewTrip.startDate} ~ ${previewTrip.endDate}`}</dd>
                        </div>
                        <div>
                          <dt>목적</dt>
                          <dd>{previewTrip.visitPurpose}</dd>
                        </div>
                      </>
                    )}
                    <div>
                      <dt>총액</dt>
                      <dd>{formatCurrency(result.preview.amount)}</dd>
                    </div>
                  </dl>
                )}
                {previewTrip?.costBreakdown && (
                  <div className="cost-summary">
                    <span>
                      교통비{' '}
                      <strong>{formatCurrency(previewTrip.costBreakdown.transportation)}</strong>
                    </span>
                    <span>
                      숙박비 <strong>{formatCurrency(previewTrip.costBreakdown.lodging)}</strong>
                    </span>
                    <span>
                      식비 <strong>{formatCurrency(previewTrip.costBreakdown.meals)}</strong>
                    </span>
                    <span>
                      기타 <strong>{formatCurrency(previewTrip.costBreakdown.other)}</strong>
                    </span>
                  </div>
                )}
              </section>

              <section className="draft-policy-card">
                <div
                  className={`policy-review-status policy-status-${result.policyContext.status.toLowerCase()}`}
                >
                  <strong>정책 검색</strong>
                  <span>
                    {result.policyContext.status === 'READY' && !result.policyContext.items.length
                      ? '관련 규정 근거를 찾지 못했습니다. 직접 확인해 주세요.'
                      : result.preview.type === 'EXPENSE' && result.policyContext.status === 'READY'
                        ? '관련 경비 규정을 찾았습니다.'
                        : policyStatusLabels[result.policyContext.status]}
                  </span>
                </div>
                {result.policyContext.items.length > 0 && (
                  <div className="policy-citation-list">
                    {result.policyContext.items.map((citation) => (
                      <article className="policy-citation" key={citation.citationKey}>
                        <div>
                          <strong>{citation.sectionTitle}</strong>
                          <code>
                            {citation.sectionId} · v{citation.version}
                          </code>
                        </div>
                        <p>{citation.excerpt}</p>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <div className="draft-confirm-panel">
                <p>저장하면 편집 가능한 초안이 저장됩니다. 자동 제출되지는 않습니다.</p>
                {!expenseVerified && <p role="alert">이 서버 응답에는 경비 검증 정보가 없습니다. 직접 작성으로 이어가 주세요.</p>}
                <button
                  className="primary-button"
                  disabled={isConfirming || !expenseVerified}
                  onClick={handleConfirm}
                  type="button"
                >
                  {isConfirming ? '초안 저장 중…' : '확인하고 초안으로 저장'}
                </button>
                <span>저장 후 양식에서 수정하고 검수한 뒤 제출할 수 있습니다.</span>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};
