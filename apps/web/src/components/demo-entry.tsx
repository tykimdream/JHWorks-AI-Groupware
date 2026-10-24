'use client';

import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { IDENTITY_CHANGED_EVENT } from '@/hooks/use-current-employee';

export const DemoEntry = ({ durationMinutes }: { durationMinutes: number }) => {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(null);
    try {
      await apiFetch('/demo/start', { method: 'POST' });
      router.replace('/');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '체험 공간을 준비하지 못했습니다. 잠시 후 다시 시도해주세요.'));
      pending.current = false; setBusy(false);
    }
  };
  return <main className="feedback-page">
    <section className="form-section feedback-form">
      <p className="eyebrow">JHWORKS · INTERACTIVE DEMO</p>
      <h1>나만의 업무 공간에서 체험하세요</h1>
      <p>가입 없이 합성 데이터로 결재를 작성하고, 결재자 역할로 전환해 승인해볼 수 있습니다.</p>
      <ol><li>경비·출장·일반·휴가 결재 작성 및 제출</li><li>결재자 역할로 전환 후 승인·반려</li><li>사용해본 의견 남기기</li></ol>
      <p>체험은 {durationMinutes}분 동안 유지됩니다. 공간당 저장 시도 20회·보호 요청 100회까지 사용할 수 있습니다.</p>
      <p className="subtle">실제 개인정보·회사 자료는 입력하지 마세요. AI 기능은 비용 보호를 위해 꺼져 있습니다.</p>
      {error && <p role="alert" className="error-banner">{error}</p>}
      <button type="button" className="primary-button" disabled={busy} onClick={start}>
        {busy ? '체험 공간 준비 중…' : '체험 시작하기'}</button>
      <a href="https://pikan.dev/ko">포트폴리오로 돌아가기</a>
    </section>
  </main>;
};

export const DemoRoleSwitcher = ({ currentRole }: { currentRole: string }) => {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const role = currentRole === 'MANAGER' ? 'author' : 'manager';
  const change = async () => {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await apiFetch('/demo/role', { method: 'POST', body: JSON.stringify({ role }) });
      // The shell hides old content during refresh, then keys children by the new identity.
      window.dispatchEvent(new Event(IDENTITY_CHANGED_EVENT));
      router.replace('/approvals');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '역할을 바꾸지 못했습니다. 다시 시도해주세요.'));
      setBusy(false);
    }
  };
  return <div>
    <button className="secondary-button" type="button" onClick={change} disabled={busy}>
      {busy ? '역할 변경 중…' : role === 'manager' ? '결재자로 체험하기' : '작성자로 돌아가기'}</button>
    {error && <p role="alert" className="error-banner">{error}</p>}
  </div>;
};
