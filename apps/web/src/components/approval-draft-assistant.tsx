'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { formatCurrency } from '@/lib/format';
import type { Approval, ApprovalDraftPrepareResponse, BusinessTripDetails } from '@/lib/types';

const starterExamples = [
  '다음 주 화요일 부산 하버랩 프로젝트 협의 출장 결재 만들어줘.',
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
  const [request, setRequest] = useState('');
  const [answers, setAnswers] = useState<string[]>([]);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<ApprovalDraftPrepareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);

  const prepare = async (nextAnswers: string[]) => {
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
    await prepare([]);
  };

  const handleFollowUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = answer.trim();
    if (!trimmed) return;
    await prepare([...answers, trimmed]);
  };

  const handleConfirm = async () => {
    if (!result?.preview || !result.confirmationToken) return;
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
      router.push(`/approvals/${approval.id}`);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, 'Draft를 저장하지 못했습니다.'));
    } finally {
      setIsConfirming(false);
    }
  };

  const reset = () => {
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
    <div className="draft-assistant-layout">
      <section className="draft-conversation-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">NATURAL LANGUAGE TO DRAFT</p>
            <h2>어떤 결재가 필요한가요?</h2>
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
                  maxLength={2000}
                  onChange={(event) => setRequest(event.target.value)}
                  placeholder="예: 다음 주 화요일 부산 고객사 미팅 출장 결재 만들어줘."
                  rows={5}
                  value={request}
                />
              </label>
              <button className="ai-button" disabled={isPreparing || !request.trim()} type="submit">
                {isPreparing ? '내용 파악 중…' : 'AI로 초안 준비'}
              </button>
            </form>
            <div className="draft-examples">
              <span>예시로 시작하기</span>
              {starterExamples.map((example) => (
                <button key={example} onClick={() => setRequest(example)} type="button">
                  {example}
                </button>
              ))}
            </div>
          </>
        )}

        {result && (
          <div className="draft-conversation">
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
                <button className="ai-button" disabled={isPreparing || !answer.trim()} type="submit">
                  {isPreparing ? '초안 갱신 중…' : '답변 반영'}
                </button>
              </form>
            )}

            {result.status === 'UNSUPPORTED' && (
              <div className="unsupported-actions">
                <Link className="secondary-button" href="/approvals/new">
                  수동으로 작성
                </Link>
              </div>
            )}
          </div>
        )}
        {error && <p className="error-banner">{error}</p>}
      </section>

      <aside className="draft-preview-column">
        {!result?.preview && (
          <div className="draft-placeholder">
            <strong>아직 저장된 문서는 없습니다.</strong>
            <p>필수 정보가 모이면 이곳에 JHWorks 전자결재 미리보기가 표시됩니다.</p>
          </div>
        )}

        {result?.preview && (
          <>
            <section className="draft-preview-card">
              <div className="preview-state">
                <span>저장 전 미리보기</span>
                <strong>{result.preview.type === 'BUSINESS_TRIP' ? '출장 신청' : '일반 결재'}</strong>
              </div>
              <h2>{result.preview.title}</h2>
              <p className="preview-content">{result.preview.content}</p>
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
              {previewTrip?.costBreakdown && (
                <div className="cost-summary">
                  <span>교통비 <strong>{formatCurrency(previewTrip.costBreakdown.transportation)}</strong></span>
                  <span>숙박비 <strong>{formatCurrency(previewTrip.costBreakdown.lodging)}</strong></span>
                  <span>식비 <strong>{formatCurrency(previewTrip.costBreakdown.meals)}</strong></span>
                  <span>기타 <strong>{formatCurrency(previewTrip.costBreakdown.other)}</strong></span>
                </div>
              )}
            </section>

            <section className="draft-policy-card">
              <div className={`policy-review-status policy-status-${result.policyContext.status.toLowerCase()}`}>
                <strong>정책 검색</strong>
                <span>{policyStatusLabels[result.policyContext.status]}</span>
              </div>
              {result.policyContext.items.length > 0 && (
                <div className="policy-citation-list">
                  {result.policyContext.items.map((citation) => (
                    <article className="policy-citation" key={citation.citationKey}>
                      <div>
                        <strong>{citation.sectionTitle}</strong>
                        <code>{citation.sectionId} · v{citation.version}</code>
                      </div>
                      <p>{citation.excerpt}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <div className="draft-confirm-panel">
              <p>저장하면 편집 가능한 DRAFT가 생성됩니다. 자동 제출되지는 않습니다.</p>
              <button className="primary-button" disabled={isConfirming} onClick={handleConfirm} type="button">
                {isConfirming ? 'Draft 저장 중…' : '확인하고 Draft로 저장'}
              </button>
              <span>{result.model} · {result.latencyMs.toLocaleString('ko-KR')}ms · {result.usage.totalTokens.toLocaleString('ko-KR')} tokens</span>
            </div>
          </>
        )}
      </aside>
    </div>
  );
};
