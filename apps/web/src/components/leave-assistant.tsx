'use client';

import { useState, type FormEvent } from 'react';

import { AvailabilityResult } from '@/components/leave-availability-explorer';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { LeaveAssistantResponse } from '@/lib/types';

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
  const [input, setInput] = useState('');
  const [request, setRequest] = useState<string | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [result, setResult] = useState<LeaveAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const reset = () => {
    setInput('');
    setRequest(null);
    setAnswers([]);
    setConversation([]);
    setResult(null);
    setError(null);
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
      const response = await apiFetch<LeaveAssistantResponse>('/leave-assistant/consult', {
        method: 'POST',
        body: JSON.stringify({ request: nextRequest, answers: nextAnswers }),
      });
      setRequest(nextRequest);
      setAnswers(nextAnswers);
      setResult(response);
      setConversation((current) => [
        ...current,
        { role: 'assistant', text: response.assistantMessage },
      ]);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '휴가 상담 결과를 만들지 못했습니다.'));
    } finally {
      setIsLoading(false);
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
      {result?.availability && <AvailabilityResult result={result.availability} />}
    </section>
  );
};
