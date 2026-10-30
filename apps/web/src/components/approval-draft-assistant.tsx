'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

import { ApiError, apiFetch, getUserErrorMessage } from '@/lib/api';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { formatCurrency } from '@/lib/format';
import { approvalTypeLabels } from '@/lib/approval-labels';
import { expenseExamples } from '@/lib/expense-examples';
import { ExpenseVerification } from '@/components/expense-verification';
import { ExpenseSummary } from '@/components/expense-summary';
import { useWorkspaceEmployee } from '@/components/app-shell';
import { readDraftRequest, clearDraftRequest } from '@/lib/draft-handoff';
import { storeManualDraft } from '@/lib/manual-draft-handoff';
import type { Approval, ApprovalDraftPrepareResponse, BusinessTripDetails } from '@/lib/types';

const starterExamples = [
  '다음 주 화요일 부산에서 열리는 협력사 미팅 출장 신청을 준비해줘. 예상 교통비는 17만원이야.',
  '문서 유형: 일반\n제목: 가상 서비스 인터뷰 결과 보고\n개요: 가상 서비스 기획을 위한 인터뷰를 진행했습니다.\n업무 내용: 기능 범위와 권한 구조를 논의했습니다.\n업무 기간: 2026년 3월\n주요 산출물: 인터뷰 정리 문서\n참여 인원: 기획팀과 개발팀',
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
                      ? '예: 코엑스 전시회 출장에 사용한 교통비 38,000원 정산해줘.'
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
              {!expenseOnly && (
                <p className="draft-support-note">
                  일반 업무를 자연어로 적어 주세요. 입력 문장을 순서대로 보존하고 지원하는 표현만 다듬습니다. 제목이나 항목을 직접 지정할 수도 있습니다.
                </p>
              )}
              <div className="draft-examples">
                <span>예시로 시작하기</span>
                {([...expenseExamples.map((example) => example.request), ...(expenseOnly ? [] : starterExamples)]).map((example) => (
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

              {result.status === 'PREVIEW' && result.preview?.type === 'GENERAL' && (
                <form className="draft-follow-up-form" onSubmit={handleFollowUp}>
                  <label>
                    <span>추가하거나 정정할 내용</span>
                    <textarea
                      maxLength={2000}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="기간, 산출물, 참여 인원 등 확인한 내용을 알려주세요."
                      rows={3}
                      value={answer}
                    />
                  </label>
                  <button className="ai-button" disabled={isPreparing || !answer.trim()} type="submit">
                    {isPreparing ? '초안 갱신 중…' : '추가 내용 반영'}
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
                {result.generalVerification === 'NATURAL_INPUT_MATCHED' && (
                  <div className="policy-review-status">
                    <strong>입력 문장에 근거한 기안</strong>
                    <span>문장 순서를 유지하고 일부 말투만 바꿨습니다. 실제 사실과 맥락은 직접 확인해 주세요.</span>
                  </div>
                )}
                {result.generalVerification === 'STRUCTURED_INPUT_MATCHED' && (
                  <div className="policy-review-status">
                    <strong>입력 근거를 확인한 기안</strong>
                    <span>입력한 항목을 서버가 그대로 구성했습니다. 실제 사실과 맥락은 직접 확인해 주세요.</span>
                  </div>
                )}
                {result.generalVerification === 'REBUILT_FROM_INPUT' && (
                  <p role="status">AI 문장이 입력과 정확히 대응하지 않아 사용자 입력으로 초안을 구성했습니다. 내용을 직접 다듬고 확인해 주세요.</p>
                )}
                {result.generalVerification === 'INPUT_MATCHED' && (
                  <p>기안 문장을 입력 내용과 대조했습니다. 실제 사실과 맥락은 직접 확인해 주세요.</p>
                )}
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

              {result.generalEvidence && result.generalEvidence.length > 0 && (
                <section className="draft-policy-card">
                  <div className="policy-review-status">
                    <strong>기안 내용의 입력 근거</strong>
                    <span>{result.generalExampleTitle
                      ? `항목명은 가상 사례 ‘${result.generalExampleTitle}’를 참고했습니다.`
                      : '입력 항목을 기준으로 구성했습니다.'}</span>
                  </div>
                  {Boolean(result.generalMissingFields?.length) && (
                    <p>사례에 있으나 입력되지 않은 항목: {result.generalMissingFields?.join(', ')}. 필요한 경우 내용을 추가해 주세요.</p>
                  )}
                  {result.generalEvidence.map((fact) => (
                    <article className="policy-citation" key={`${fact.sourceIndex}-${fact.start}-${fact.end}`}>
                      <strong>{fact.field} · {fact.sourceIndex === 0 ? '업무 요청' : `추가 답변 ${fact.sourceIndex}`}</strong>
                      <p>입력: {fact.text}</p>
                      {fact.transformation && fact.transformation !== 'EXACT' && <p>기안: {fact.draftText}</p>}
                    </article>
                  ))}
                </section>
              )}
              <section className="draft-policy-card">
                <div className="policy-review-status">
                  <strong>결재선 안내</strong>
                  <span>{result.approverSuggestion
                    ? `${result.approverSuggestion.name} · ${result.approverSuggestion.position} — ${result.approverSuggestion.reason}`
                    : '현재 지정 가능한 직속 상급자가 없습니다. 제출 전 조직 정보를 확인해 주세요.'}</span>
                </div>
                <p>현재 결재선은 직속 상급자 1명이며 제출할 때 지정됩니다.</p>
              </section>
              {result.preview.type === 'GENERAL' && (
                <section className="draft-policy-card">
                  <div className="policy-review-status">
                    <strong>참고한 가상 기안 사례</strong>
                    <span>{result.exampleStatus === 'READY'
                      ? (result.examples?.length ? '가상 사례를 검색했습니다. 기안의 사실과 확인 필요 항목을 검토해 주세요.' : '관련 사례를 찾지 못했습니다.')
                      : '사례 검색을 사용할 수 없어 사용자 입력으로만 작성했습니다.'}</span>
                  </div>
                  {result.exampleRetrieval === 'LOCAL' && <p>업무 내용은 이 서버의 로컬 모델에서 검색했습니다.</p>}
                  {result.exampleRetrieval === 'SAFE_TOPICS_AFTER_LOCAL_FAILURE' && <p>로컬 검색을 사용할 수 없어 업무 유형으로 검색했습니다.</p>}
                  {result.examples?.map((example) => (
                    <article className="policy-citation" key={example.id}>
                      <strong>{example.title}</strong>
                      <p>{example.outline.join(' · ')}</p>
                      <details>
                        <summary>가상 예시 본문 보기</summary>
                        <p className="preview-content">{example.content}</p>
                      </details>
                    </article>
                  ))}
                </section>
              )}
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
