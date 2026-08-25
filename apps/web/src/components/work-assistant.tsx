'use client';

import { useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { WorkAssistantResponse, WorkAssistantToolExecution } from '@/lib/types';

const examples = [
  '내 남은 연차가 며칠이야?',
  '내 직속 관리자가 누구야?',
  '내가 올린 결재 중 대기 중인 문서 보여줘.',
  '국내 출장 숙박비 한도를 회사 규정 근거와 함께 알려줘.',
];

const toolLabels: Record<string, string> = {
  get_current_employee: '현재 사용자 조회',
  get_my_manager: '직속 관리자 조회',
  list_my_approvals: '내 결재 조회',
  search_company_policy: '사내 정책 검색',
};

const executionSummary = (execution: WorkAssistantToolExecution): string => {
  if (execution.name === 'get_current_employee') {
    const employee = execution.result.employee as Record<string, unknown> | undefined;
    return employee ? `${String(employee.name)} · 잔여 연차 ${String(employee.leaveBalanceDays)}일` : '조회 완료';
  }
  if (execution.name === 'get_my_manager') {
    const manager = execution.result.manager as Record<string, unknown> | null | undefined;
    return manager ? `${String(manager.name)} · ${String(manager.position)}` : '지정된 관리자가 없습니다.';
  }
  if (execution.name === 'list_my_approvals') {
    return `${String(execution.result.total ?? 0)}건 조회`;
  }
  if (execution.name === 'search_company_policy') {
    const items = execution.result.items as unknown[] | undefined;
    return `${String(execution.result.status)} · ${items?.length ?? 0}개 섹션`;
  }
  return '실행 완료';
};

export const WorkAssistant = () => {
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<WorkAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) return;
    setError(null);
    setResult(null);
    setIsLoading(true);
    try {
      const response = await apiFetch<WorkAssistantResponse>('/work-assistant/query', {
        method: 'POST',
        body: JSON.stringify({ message }),
      });
      setResult(response);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '업무 정보를 조회하지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="work-assistant-layout">
      <section className="work-query-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">READ-ONLY ENTERPRISE TOOLS</p>
            <h2>업무 정보를 물어보세요</h2>
          </div>
          <span className="read-only-badge">조회 전용</span>
        </div>
        <p className="subtle">
          AI는 필요한 JHWorks Tool만 선택해 현재 사용자 권한으로 조회합니다. 데이터를 변경하는 Tool은 없습니다.
        </p>
        <form className="work-query-form" onSubmit={handleSubmit}>
          <label>
            <span>질문</span>
            <textarea
              maxLength={2000}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="예: 내 결재 중 아직 승인되지 않은 문서 보여줘."
              rows={5}
              value={message}
            />
          </label>
          <button className="ai-button" disabled={isLoading || !message.trim()} type="submit">
            {isLoading ? '업무 데이터 확인 중…' : 'AI에게 조회 요청'}
          </button>
        </form>
        <div className="work-query-examples">
          <span>예시 질문</span>
          {examples.map((example) => (
            <button key={example} onClick={() => setMessage(example)} type="button">
              {example}
            </button>
          ))}
        </div>
        {error && <p className="error-banner">{error}</p>}
      </section>

      <section className="work-answer-card">
        {!result && !isLoading && (
          <div className="work-answer-placeholder">
            <strong>아직 조회 결과가 없습니다.</strong>
            <p>답변에는 실제 실행된 Tool과 정책 근거가 함께 표시됩니다.</p>
          </div>
        )}
        {isLoading && <div className="work-answer-placeholder">안전한 조회 범위를 확인하고 있습니다.</div>}
        {result && (
          <>
            <div className="assistant-answer">
              <p className="eyebrow">JHWORKS AI ANSWER</p>
              <p>{result.answer}</p>
            </div>
            <div className="tool-audit-list">
              <div className="section-heading">
                <h2>실행된 Tool</h2>
                <span className="subtle">{result.toolExecutions.length}회</span>
              </div>
              {result.toolExecutions.length === 0 && (
                <p className="subtle">업무 데이터 조회가 필요하지 않은 질문입니다.</p>
              )}
              {result.toolExecutions.map((execution, index) => (
                <details className="tool-audit-item" key={`${execution.name}-${index}`}>
                  <summary>
                    <span>{toolLabels[execution.name] ?? execution.name}</span>
                    <strong>{executionSummary(execution)}</strong>
                  </summary>
                  <div>
                    <span>입력</span>
                    <pre>{JSON.stringify(execution.arguments, null, 2)}</pre>
                    <span>서버 결과</span>
                    <pre>{JSON.stringify(execution.result, null, 2)}</pre>
                  </div>
                </details>
              ))}
            </div>
            {result.policyCitations.length > 0 && (
              <div className="assistant-policy-evidence">
                <h2>정책 근거</h2>
                <div className="policy-citation-list">
                  {result.policyCitations.map((citation) => (
                    <article className="policy-citation" key={citation.citationKey}>
                      <div>
                        <strong>{citation.sectionTitle}</strong>
                        <code>{citation.citationKey}</code>
                      </div>
                      <p>{citation.excerpt}</p>
                    </article>
                  ))}
                </div>
              </div>
            )}
            <p className="assistant-runtime">
              {result.model} · {result.roundCount} rounds · {result.latencyMs.toLocaleString('ko-KR')}ms ·{' '}
              {result.usage.totalTokens.toLocaleString('ko-KR')} tokens
            </p>
          </>
        )}
      </section>
    </div>
  );
};
