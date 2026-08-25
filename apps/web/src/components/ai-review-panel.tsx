'use client';

import { useState } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { AIReview, Approval, ReviewCategory, ReviewSeverity } from '@/lib/types';

const severityLabels: Record<ReviewSeverity, string> = {
  HIGH: '높음',
  MEDIUM: '중간',
  LOW: '낮음',
  INFO: '참고',
};

const categoryLabels: Record<ReviewCategory, string> = {
  COMPLETENESS: '완성도',
  CLARITY: '명확성',
  WRITING: '표현',
  RISK: '위험',
  POLICY: '회사 정책',
};

const sourceLabels = {
  DETERMINISTIC: '규칙 검사',
  LLM: 'AI 판단',
  POLICY: '정책 근거',
} as const;

const policyStatusMessages = {
  READY: '회사 정책 검색과 인용 검증을 완료했습니다.',
  NOT_APPLICABLE: '이 문서 유형에는 적용할 정책 검색이 없습니다.',
  NOT_INDEXED: '정책 인덱스가 준비되지 않아 일반 문서 검토만 수행했습니다.',
  UNAVAILABLE: '정책 검색을 사용할 수 없어 일반 문서 검토만 수행했습니다.',
} as const;

interface AIReviewPanelProps {
  approval: Approval;
  canReview: boolean;
  onApprovalUpdated: (approval: Approval) => void;
}

export const AIReviewPanel = ({
  approval,
  canReview,
  onApprovalUpdated,
}: AIReviewPanelProps) => {
  const [review, setReview] = useState<AIReview | null>(null);
  const [revisionContent, setRevisionContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  if (!canReview) {
    return null;
  }

  const runReview = async () => {
    setIsReviewing(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await apiFetch<AIReview>(`/approvals/${approval.id}/ai-review`, {
        method: 'POST',
        body: JSON.stringify({ version: approval.version }),
      });
      setReview(result);
      setRevisionContent(result.revisedContent?.trim() ? result.revisedContent : approval.content);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, 'AI 검토를 완료하지 못했습니다.'));
    } finally {
      setIsReviewing(false);
    }
  };

  const applyRevision = async () => {
    if (!review || review.isStale || review.approvalVersion !== approval.version) {
      setError('문서가 변경되었습니다. 현재 버전에서 AI 검토를 다시 실행해주세요.');
      return;
    }
    if (!revisionContent.trim()) {
      setError('수정할 본문 내용을 입력해주세요.');
      return;
    }
    if (revisionContent.trim() === approval.content.trim()) {
      setError('현재 본문과 다른 내용을 입력해주세요.');
      return;
    }

    setIsApplying(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiFetch<Approval>(`/approvals/${approval.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          type: approval.type,
          title: approval.title,
          content: revisionContent,
          amount: approval.amount,
          details: approval.details,
          attachmentMetadata: approval.attachmentMetadata,
          version: approval.version,
        }),
      });
      setReview((current) => current && ({
        ...current,
        currentApprovalVersion: updated.version,
        isStale: true,
      }));
      setRevisionContent(updated.content);
      setSuccessMessage(`수정한 본문을 문서 v${updated.version}에 반영했습니다.`);
      onApprovalUpdated(updated);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '수정한 본문을 반영하지 못했습니다.'));
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div
      aria-label="제출 전 AI 검토"
      aria-live="polite"
      className="ai-review-card"
      role="region"
    >
      <div className="ai-review-heading">
        <div>
          <p className="eyebrow">AI PRE-SUBMISSION REVIEW</p>
          <h2>제출 전 AI 검토</h2>
          <p>문서의 누락과 표현을 검토하고, 관련 회사 정책을 정확한 섹션과 함께 인용합니다.</p>
        </div>
        <button
          className="ai-button"
          disabled={isReviewing}
          onClick={runReview}
          type="button"
        >
          {isReviewing ? '검토 중…' : review ? '다시 검토하기' : 'AI로 검토하기'}
        </button>
      </div>

      {error && <p className="error-banner">{error}</p>}

      {review && (
        <div className="ai-review-result">
          {successMessage && <p className="review-success-banner" role="status">{successMessage}</p>}
          {review.isStale && !successMessage && (
            <p className="stale-banner">
              문서가 변경되어 이 결과는 참고용입니다. 현재 버전에서 다시 검토해주세요.
            </p>
          )}

          <div className="ai-review-workspace">
            <div className="review-analysis-column">
              <div className="review-summary">
                <div className={`review-score review-score-${review.status.toLowerCase()}`}>
                  <strong>{review.score}</strong>
                  <span>/ 100</span>
                </div>
                <div>
                  <strong>{review.status === 'PASS' ? '제출 전 검토를 통과했습니다.' : '수정할 항목이 있습니다.'}</strong>
                  <p>{review.issues.length}개의 검토 항목 · 문서 v{review.approvalVersion}</p>
                </div>
              </div>

              <div className={`policy-review-status policy-status-${review.policyReview.status.toLowerCase()}`}>
                <strong>정책 검토</strong>
                <span>{policyStatusMessages[review.policyReview.status]}</span>
                {review.policyReview.status === 'READY' && (
                  <small>
                    {review.policyReview.retrievedCitations.length}개 섹션 검색 ·{' '}
                    {review.policyReview.model} · {review.policyReview.latencyMs.toLocaleString()}ms
                  </small>
                )}
              </div>

              {review.issues.length > 0 && (
                <div className="review-issue-list">
                  {review.issues.map((issue) => (
                    <article className={`review-issue severity-${issue.severity.toLowerCase()}`} key={issue.code}>
                      <div className="review-issue-meta">
                        <span>{severityLabels[issue.severity]}</span>
                        <span>{categoryLabels[issue.category]}</span>
                        <span>{sourceLabels[issue.source]}</span>
                        <code>{issue.field}</code>
                      </div>
                      <strong>{issue.message}</strong>
                      {issue.suggestion && <p>{issue.suggestion}</p>}
                      {issue.citations.length > 0 && (
                        <div className="policy-citation-list">
                          {issue.citations.map((citation) => (
                            <blockquote className="policy-citation" key={citation.citationKey}>
                              <div>
                                <strong>{citation.policyTitle}</strong>
                                <code>
                                  v{citation.version} · {citation.sectionId} · {citation.sectionTitle}
                                </code>
                              </div>
                              <p>{citation.excerpt}</p>
                              <small>
                                검색 유사도 {citation.similarityScore.toFixed(3)} · 원문에서 확인된 근거
                              </small>
                            </blockquote>
                          ))}
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </div>

            <section className="review-revision-editor">
              <div>
                <p className="eyebrow">EDITABLE EXAMPLE</p>
                <h3>AI 수정 예시</h3>
                <p>
                  {review.revisedContent?.trim()
                    && review.revisedContent.trim() !== approval.content.trim()
                    ? 'AI 제안을 바로 다듬은 뒤 Draft 본문에 반영할 수 있습니다.'
                    : 'AI가 현재 본문을 유지했습니다. 필요한 내용을 직접 다듬어 반영할 수 있습니다.'}
                </p>
              </div>
              <label htmlFor="ai-review-revision">수정할 본문</label>
              <textarea
                disabled={review.isStale || isApplying}
                id="ai-review-revision"
                maxLength={5000}
                onChange={(event) => {
                  setRevisionContent(event.target.value);
                  setError(null);
                  setSuccessMessage(null);
                }}
                rows={16}
                value={revisionContent}
              />
              <div className="review-revision-actions">
                <span>{revisionContent.length.toLocaleString()} / 5,000자</span>
                <button
                  className="primary-button"
                  disabled={
                    isApplying
                    || review.isStale
                    || !revisionContent.trim()
                    || revisionContent.trim() === approval.content.trim()
                  }
                  onClick={applyRevision}
                  type="button"
                >
                  {isApplying ? '반영 중…' : '수정하기'}
                </button>
              </div>
              <small>버튼을 누르기 전에는 원문이 변경되지 않습니다.</small>
            </section>
          </div>

          <div className="review-runtime">
            <span>{review.model}</span>
            <span>{review.promptVersion}</span>
            <span>{review.latencyMs.toLocaleString()}ms</span>
            <span>{review.usage.totalTokens.toLocaleString()} tokens</span>
          </div>
        </div>
      )}
    </div>
  );
};
