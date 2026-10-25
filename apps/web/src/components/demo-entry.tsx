'use client';

import Link from 'next/link';
import { PublicPageHeader } from '@/components/brand-logo';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { notifyIdentityChanged } from '@/lib/session-events';

export const DemoEntry = ({
  durationMinutes,
  expenseAiAvailable = false,
}: {
  durationMinutes: number;
  expenseAiAvailable?: boolean;
}) => {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      await apiFetch('/demo/start', { method: 'POST' });
      notifyIdentityChanged();
      router.replace('/');
    } catch (caught: unknown) {
      setError(
        getUserErrorMessage(caught, '체험 공간을 준비하지 못했습니다. 잠시 후 다시 시도해주세요.'),
      );
      pending.current = false;
      setBusy(false);
    }
  };
  return (
    <main className="feedback-page">
      <PublicPageHeader />
      <section className="form-section feedback-form">
        <p className="eyebrow">JHWORKS · INTERACTIVE DEMO</p>
        <h1>경비 정산, 작성부터 승인까지</h1>
        <p>
          예시 데이터로 경비를 작성하고 직접 승인해 보세요. 작성자와 결재자 역할을 모두 체험할 수
          있습니다.
        </p>
        <ol>
          <li>경비를 작성하고 초안으로 저장</li>
          <li>내용을 확인하고 결재 요청</li>
          <li>결재자가 되어 승인 결과 확인</li>
        </ol>
        <p>가입 없이 · {durationMinutes}분 체험 · 방문자별 전용 공간</p>
        <p className="subtle">
          실제 개인정보나 회사 자료를 입력하지 마세요. {expenseAiAvailable
            ? 'AI 경비 초안을 준비할 수 있으며, 이용 한도에 도달하면 직접 작성할 수 있습니다.'
            : '이 체험에서는 AI 호출을 제공하지 않습니다.'}
        </p>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        <button type="button" className="primary-button" disabled={busy} onClick={start}>
          {busy ? '체험 공간 준비 중…' : '체험 시작하기'}
        </button>
        <details>
          <summary>체험 범위와 이용 안내</summary>
          <p>
            경비·출장·일반·휴가 결재를 작성할 수 있습니다. 공간별 저장 시도는 20회로 제한되며,
            이용량이나 보관 한도에 따라 새 체험이 중단될 수 있습니다.
          </p>
        </details>
        <p>
          <Link href="/pattern">JHW Pattern 살펴보기</Link> ·{' '}
          <a href="https://pikan.dev/ko">포트폴리오로 돌아가기</a>
        </p>
      </section>
    </main>
  );
};

export const DemoRoleSwitcher = ({
  currentRole,
  label,
  fullWidth = false,
}: {
  currentRole: string;
  label?: string;
  fullWidth?: boolean;
}) => {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const role = currentRole === 'MANAGER' ? 'author' : 'manager';
  const change = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch('/demo/role', { method: 'POST', body: JSON.stringify({ role }) });
      // The shell hides old content during refresh, then keys children by the new identity.
      notifyIdentityChanged();
      router.replace(role === 'manager' ? '/approvals?scope=assigned' : '/approvals');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '역할을 바꾸지 못했습니다. 다시 시도해주세요.'));
      setBusy(false);
    }
  };
  return (
    <div>
      <button
        className={`secondary-button${fullWidth ? ' tw:w-full' : ''}`}
        type="button"
        onClick={change}
        disabled={busy}
      >
        {busy
          ? '역할 변경 중…'
          : (label ?? (role === 'manager' ? '결재자로 체험하기' : '작성자로 돌아가기'))}
      </button>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
    </div>
  );
};
