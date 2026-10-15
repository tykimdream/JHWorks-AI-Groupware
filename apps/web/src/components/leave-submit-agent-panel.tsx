'use client';

import { useEffect, useState } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
  Approval,
  LeaveAgentRun,
  LeaveSubmitPreparation,
  LeaveSubmitResumeResult,
} from '@/lib/types';

export const LeaveSubmitAgentPanel = ({
  approval,
  runId,
  onApprovalUpdated,
}: {
  approval: Approval;
  runId: string;
  onApprovalUpdated: (approval: Approval) => void;
}) => {
  const [run, setRun] = useState<LeaveAgentRun | null>(null);
  const [preparation, setPreparation] = useState<LeaveSubmitPreparation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isResuming, setIsResuming] = useState(false);

  useEffect(() => {
    apiFetch<LeaveAgentRun>(`/leave-agent/runs/${runId}`)
      .then(setRun)
      .catch((caught: unknown) => {
        setError(getUserErrorMessage(caught, '휴가 workflow를 불러오지 못했습니다.'));
      });
  }, [runId]);

  const refreshRun = async () => {
    try {
      setRun(await apiFetch<LeaveAgentRun>(`/leave-agent/runs/${runId}`));
    } catch {
      // The original action error remains the most useful message.
    }
  };

  const prepare = async () => {
    setError(null);
    setIsPreparing(true);
    try {
      const prepared = await apiFetch<LeaveSubmitPreparation>(
        `/leave-agent/runs/${runId}/submit/prepare`,
        {
          method: 'POST',
          body: JSON.stringify({ approvalVersion: approval.version }),
        },
      );
      setPreparation(prepared);
      setRun(prepared.run);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '제출 미리보기를 준비하지 못했습니다.'));
      await refreshRun();
    } finally {
      setIsPreparing(false);
    }
  };

  const resume = async (decision: 'CONFIRM' | 'CANCEL') => {
    if (!preparation) return;
    setError(null);
    setIsResuming(true);
    try {
      const resumed = await apiFetch<LeaveSubmitResumeResult>(
        `/leave-agent/runs/${runId}/submit/resume`,
        {
          method: 'POST',
          body: JSON.stringify({
            decision,
            preview: preparation.preview,
            confirmationToken: preparation.confirmationToken,
          }),
        },
      );
      setRun(resumed.run);
      onApprovalUpdated(resumed.approval);
      if (decision === 'CANCEL') setPreparation(null);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '제출 workflow를 재개하지 못했습니다.'));
      await refreshRun();
    } finally {
      setIsResuming(false);
    }
  };

  return (
    <section className="leave-submit-agent" aria-label="휴가 제출 Agent">
      <div className="section-heading">
        <div>
          <p className="eyebrow">DURABLE SUBMIT AGENT</p>
          <h2>별도 제출 확인</h2>
        </div>
        <span className="read-only-badge">{run?.status ?? 'LOADING'}</span>
      </div>
      {!preparation && approval.status === 'DRAFT' && run?.status !== 'CANCELED' && (
        <div className="action-panel">
          <div>
            <strong>Draft 저장 확인은 완료되었습니다.</strong>
            <p>제출은 현재 상태를 다시 계산한 별도 미리보기와 두 번째 확인이 필요합니다.</p>
          </div>
          <button className="primary-button" disabled={isPreparing} onClick={prepare} type="button">
            {isPreparing ? '제출 조건 계산 중…' : '제출 미리보기 준비'}
          </button>
        </div>
      )}

      {preparation && approval.status === 'DRAFT' && (
        <div className="leave-submit-preview">
          <div className="preview-state">
            <span>두 번째 확인 대기</span>
            <strong>아직 제출되지 않음</strong>
          </div>
          <dl className="preview-detail-grid">
            <div><dt>Approval version</dt><dd>v{preparation.preview.approvalVersion}</dd></div>
            <div><dt>차감</dt><dd>{preparation.preview.requestedDays}일</dd></div>
            <div><dt>현재 가용</dt><dd>{preparation.preview.availableDays}일</dd></div>
            <div><dt>현재 대기</dt><dd>{preparation.preview.pendingDays}일</dd></div>
            <div><dt>최종 결재자</dt><dd>{preparation.preview.managerName} · {preparation.preview.managerPosition}</dd></div>
            <div><dt>계정 version</dt><dd>v{preparation.preview.accountVersion}</dd></div>
          </dl>
          {preparation.preview.warnings.length > 0 && (
            <div className="availability-notice">
              {preparation.preview.warnings.map((warning) => (
                <p key={warning.code}>{warning.message}</p>
              ))}
            </div>
          )}
          <p className="subtle">
            확인 직전에 status, version, 결재자, 연차 계정과 캘린더를 다시 검증합니다. 만료·취소·stale이면 Draft를 변경하지 않습니다.
          </p>
          <div className="leave-assistant-actions">
            <button className="ghost-button" disabled={isResuming} onClick={() => resume('CANCEL')} type="button">
              제출 취소
            </button>
            <button className="primary-button" disabled={isResuming} onClick={() => resume('CONFIRM')} type="button">
              {isResuming ? '최종 재검증 중…' : '내용을 확인했고 제출'}
            </button>
          </div>
        </div>
      )}

      {run?.status === 'CANCELED' && (
        <p className="stale-banner">제출을 취소했습니다. Draft와 연차 계정은 변경되지 않았습니다.</p>
      )}
      {run?.status === 'FAILED' && (
        <p className="stale-banner">Tool 실패 상태가 저장되었습니다. 같은 확인으로 안전하게 다시 시도할 수 있습니다.</p>
      )}
      {run?.status === 'SUBMITTED' && (
        <p className="review-success-banner">두 번째 확인이 완료되어 직속 관리자에게 제출했습니다.</p>
      )}
      {error && <p className="error-banner">{error}</p>}
      {run && (
        <div className="leave-agent-runtime">
          <span>durable run</span>
          <code>{run.id}</code>
          <strong>{run.status}</strong>
          <span>{run.trace.length} transitions · retry {run.retryCount}</span>
        </div>
      )}
    </section>
  );
};
