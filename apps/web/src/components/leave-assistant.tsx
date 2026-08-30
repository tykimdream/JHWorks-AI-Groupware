'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { AvailabilityResult } from '@/components/leave-availability-explorer';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
  LeaveAssistantResponse,
  LeaveAgentConsultation,
  LeaveAgentDraftConfirmation,
  LeaveAgentDraftPreparation,
  LeaveAgentRun,
  LeaveAvailabilityCandidate,
  LeaveDetails,
  LeaveDraftPrepareResponse,
} from '@/lib/types';

const examples = [
  '다음 주 목요일과 금요일 연차 가능한지 알려줘.',
  '9월에 이틀 쉴 날짜 추천해줘.',
];

interface ConversationItem {
  role: 'user' | 'assistant';
  text: string;
}

const dateRangeLabel = (result: LeaveAssistantResponse) => {
  if (!result.query.searchStart || !result.query.searchEnd) return '날짜 확인 필요';
  return `${result.query.searchStart} → ${result.query.searchEnd}`;
};

export const LeaveAssistant = () => {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [request, setRequest] = useState<string | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [result, setResult] = useState<LeaveAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [draftResult, setDraftResult] = useState<LeaveDraftPrepareResponse | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isPreparingDraft, setIsPreparingDraft] = useState(false);
  const [isConfirmingDraft, setIsConfirmingDraft] = useState(false);
  const [agentRun, setAgentRun] = useState<LeaveAgentRun | null>(null);

  const reset = () => {
    setInput('');
    setRequest(null);
    setAnswers([]);
    setConversation([]);
    setResult(null);
    setError(null);
    setDraftResult(null);
    setDraftError(null);
    setAgentRun(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = input.trim();
    if (!message) return;
    const nextRequest = request ?? message;
    const nextAnswers = request ? [...answers, message] : [];
    setConversation((current) => [...current, { role: 'user', text: message }]);
    setInput('');
    setError(null);
    setIsLoading(true);
    try {
      const response = request && agentRun
        ? await apiFetch<LeaveAgentConsultation>(
            `/leave-agent/runs/${agentRun.id}/consultation/answer`,
            { method: 'POST', body: JSON.stringify({ answer: message }) },
          )
        : await apiFetch<LeaveAgentConsultation>('/leave-agent/runs', {
            method: 'POST',
            body: JSON.stringify({ request: nextRequest, answers: nextAnswers }),
          });
      setRequest(nextRequest);
      setAnswers(nextAnswers);
      setAgentRun(response.run);
      setResult(response.consultation);
      setDraftResult(null);
      if (response.consultation) {
        setConversation((current) => [
          ...current,
          { role: 'assistant', text: response.consultation?.assistantMessage ?? '' },
        ]);
      } else {
        setError('AI 구조화 단계가 일시적으로 실패했습니다. 저장된 workflow에서 다시 시도할 수 있습니다.');
      }
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '휴가 상담 결과를 만들지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  };

  const retryConsultation = async () => {
    if (!agentRun) return;
    setError(null);
    setIsLoading(true);
    try {
      const response = await apiFetch<LeaveAgentConsultation>(
        `/leave-agent/runs/${agentRun.id}/consultation/retry`,
        { method: 'POST' },
      );
      setAgentRun(response.run);
      setResult(response.consultation);
      if (response.consultation) {
        setConversation((current) => [
          ...current,
          { role: 'assistant', text: response.consultation?.assistantMessage ?? '' },
        ]);
      }
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '상담 workflow를 재개하지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  };

  const prepareDraft = async (candidate: LeaveAvailabilityCandidate) => {
    if (!agentRun) return;
    setDraftError(null);
    setDraftResult(null);
    setIsPreparingDraft(true);
    try {
      const prepared = await apiFetch<LeaveAgentDraftPreparation>(
        `/leave-agent/runs/${agentRun.id}/draft/prepare`,
        {
          method: 'POST',
          body: JSON.stringify({
            candidate,
            leaveUnit: candidate.requestedDays === '0.5' ? 'HALF_DAY_AM' : 'FULL_DAY',
          }),
        },
      );
      setAgentRun(prepared.run);
      setDraftResult(prepared.preparation);
    } catch (caught: unknown) {
      setDraftError(getUserErrorMessage(caught, '휴가 Draft 미리보기를 만들지 못했습니다.'));
    } finally {
      setIsPreparingDraft(false);
    }
  };

  const confirmDraft = async () => {
    if (!draftResult || !agentRun) return;
    setDraftError(null);
    setIsConfirmingDraft(true);
    try {
      const confirmed = await apiFetch<LeaveAgentDraftConfirmation>(
        `/leave-agent/runs/${agentRun.id}/draft/confirm`,
        {
          method: 'POST',
          body: JSON.stringify({
            preview: draftResult.preview,
            confirmationToken: draftResult.confirmationToken,
          }),
        },
      );
      setAgentRun(confirmed.run);
      router.push(`/approvals/${confirmed.approval.id}?leaveRunId=${confirmed.run.id}`);
    } catch (caught: unknown) {
      setDraftError(getUserErrorMessage(caught, '휴가 Draft를 저장하지 못했습니다.'));
    } finally {
      setIsConfirmingDraft(false);
    }
  };

  return (
    <section className="leave-assistant-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">GROUNDED LEAVE ASSISTANT</p>
          <h2>자연어로 휴가 상담</h2>
        </div>
        <span className="read-only-badge">조회 전용</span>
      </div>
      <p className="subtle">
        AI는 요청을 실제 날짜로 정리합니다. 가능 여부와 차감·충돌은 현재 연차 계정과 JHWorks 일정으로 서버가 계산합니다.
      </p>

      {conversation.length > 0 && (
        <div className="leave-conversation" aria-live="polite">
          {conversation.map((item, index) => (
            <div className={`leave-message ${item.role}`} key={`${item.role}-${index}`}>
              <span>{item.role === 'user' ? '나' : 'JHWorks AI'}</span>
              <p>{item.text}</p>
            </div>
          ))}
        </div>
      )}

      <form className="leave-assistant-form" onSubmit={handleSubmit}>
        <label>
          <span>{request ? '추가 답변' : '휴가 질문'}</span>
          <textarea
            maxLength={2000}
            onChange={(event) => setInput(event.target.value)}
            placeholder={request ? result?.questions[0]?.prompt : examples[0]}
            rows={3}
            value={input}
          />
        </label>
        <div className="leave-assistant-actions">
          {request && (
            <button className="ghost-button" onClick={reset} type="button">
              새 상담
            </button>
          )}
          <button className="ai-button" disabled={isLoading || !input.trim()} type="submit">
            {isLoading ? '정책과 일정 확인 중…' : request ? '답변 보내기' : '휴가 상담 시작'}
          </button>
        </div>
      </form>
      {!request && conversation.length === 0 && (
        <div className="leave-assistant-examples">
          {examples.map((example) => (
            <button key={example} onClick={() => setInput(example)} type="button">
              {example}
            </button>
          ))}
        </div>
      )}
      {error && <p className="error-banner">{error}</p>}
      {agentRun?.status === 'CONSULTATION_FAILED' && (
        <button className="secondary-button" disabled={isLoading} onClick={retryConsultation} type="button">
          저장된 상담에서 다시 시도
        </button>
      )}

      {agentRun && (
        <div className="leave-agent-runtime">
          <span>durable run</span>
          <code>{agentRun.id}</code>
          <strong>{agentRun.status}</strong>
          <span>{agentRun.trace.length} transitions · retry {agentRun.retryCount}</span>
        </div>
      )}

      {result && (
        <div className="leave-assistant-result">
          <div className="leave-query-facts">
            <div><span>확정 탐색 범위</span><strong>{dateRangeLabel(result)}</strong></div>
            <div><span>희망 일수</span><strong>{result.query.requestedDays ? `${result.query.requestedDays}일` : '확인 필요'}</strong></div>
            <div><span>정책 검색</span><strong>{result.policyContext.status}</strong></div>
          </div>
          {result.policyContext.items.length > 0 && (
            <div className="assistant-policy-evidence">
              <h3>활성 휴가 정책 근거</h3>
              <div className="policy-citation-list">
                {result.policyContext.items.map((citation) => (
                  <article className="policy-citation" key={citation.citationKey}>
                    <div><strong>{citation.sectionTitle}</strong><code>{citation.citationKey}</code></div>
                    <p>{citation.excerpt}</p>
                  </article>
                ))}
              </div>
            </div>
          )}
          <p className="assistant-runtime">
            {result.model} · {result.promptVersion} · {result.latencyMs.toLocaleString('ko-KR')}ms · {result.usage.totalTokens.toLocaleString('ko-KR')} tokens
          </p>
        </div>
      )}
      {result?.availability && (
        <AvailabilityResult
          candidateActionDisabled={isPreparingDraft}
          candidateActionLabel={isPreparingDraft ? '미리보기 준비 중…' : '이 날짜로 exact preview 만들기'}
          onCandidateSelect={prepareDraft}
          result={result.availability}
        />
      )}
      {draftError && <p className="error-banner">{draftError}</p>}
      {draftResult && (
        <LeaveDraftPreview
          isConfirming={isConfirmingDraft}
          onCancel={() => setDraftResult(null)}
          onConfirm={confirmDraft}
          result={draftResult}
        />
      )}
    </section>
  );
};

const leaveUnitLabels = {
  FULL_DAY: '종일 연차',
  HALF_DAY_AM: '오전 반차',
  HALF_DAY_PM: '오후 반차',
} as const;

const LeaveDraftPreview = ({
  result,
  isConfirming,
  onCancel,
  onConfirm,
}: {
  result: LeaveDraftPrepareResponse;
  isConfirming: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) => {
  const preview = result.preview;
  const details = preview.approval.details as LeaveDetails;
  return (
    <section className="leave-draft-preview" aria-label="휴가 Draft exact preview">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED EXACT PREVIEW</p>
          <h2>저장 전 최종 확인</h2>
        </div>
        <span className="read-only-badge">아직 저장되지 않음</span>
      </div>
      <h3>{preview.approval.title}</h3>
      <p>{preview.approval.content}</p>
      <dl className="preview-detail-grid">
        <div><dt>실제 날짜</dt><dd>{details.startDate} → {details.endDate}</dd></div>
        <div><dt>차감</dt><dd>{preview.requestedDays}일</dd></div>
        <div><dt>단위</dt><dd>{leaveUnitLabels[preview.leaveUnit]}</dd></div>
        <div><dt>현재 가용 연차</dt><dd>{preview.availableDays}일</dd></div>
        <div><dt>결재자</dt><dd>{preview.manager.name} · {preview.manager.position}</dd></div>
        <div><dt>계정 version</dt><dd>v{preview.accountVersion}</dd></div>
      </dl>
      {preview.warnings.length > 0 && (
        <div className="availability-notice">
          {preview.warnings.map((warning) => <p key={warning.code}>{warning.message}</p>)}
        </div>
      )}
      <div className="assistant-policy-evidence">
        <h3>저장에 결합된 정책 근거</h3>
        <div className="policy-citation-list">
          {preview.policyContext.items.map((citation) => (
            <article className="policy-citation" key={citation.citationKey}>
              <div><strong>{citation.sectionTitle}</strong><code>{citation.citationKey}</code></div>
              <p>{citation.excerpt}</p>
            </article>
          ))}
        </div>
      </div>
      <p className="subtle">
        확인 시 연차 계정, 일정, 결재자, 활성 정책과 이 미리보기를 다시 검증합니다. 저장 결과는 DRAFT이며 자동 제출되지 않습니다.
      </p>
      <div className="leave-assistant-actions">
        <button className="ghost-button" disabled={isConfirming} onClick={onCancel} type="button">취소</button>
        <button className="primary-button" disabled={isConfirming} onClick={onConfirm} type="button">
          {isConfirming ? '재검증 후 저장 중…' : '내용을 확인했고 Draft로 저장'}
        </button>
      </div>
    </section>
  );
};
