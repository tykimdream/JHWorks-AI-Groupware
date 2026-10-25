'use client';

import { BrandLogo } from '@/components/brand-logo';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { ApiError, apiFetch } from '@/lib/api';
import { notifyIdentityChanged } from '@/lib/session-events';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { DemoEntry } from '@/components/demo-entry';
import type { CurrentEmployee } from '@/lib/types';

const demoAccounts = [
  {
    label: '작성자 · 윤서진',
    email: 'seojin.yoon@jhworks.test',
    description: '경비·출장·휴가 결재 작성',
  },
  {
    label: '결재자 · 최도윤',
    email: 'doyun.choi@jhworks.test',
    description: '배정 문서 승인과 반려',
  },
  {
    label: '정책 운영 · 한가람',
    email: 'garam.han@jhworks.test',
    description: '가상 정책 데이터 확인',
  },
];

export default function LoginPage() {
  const { configuration, error: configurationError } = useDemoConfiguration();
  const router = useRouter();
  const [email, setEmail] = useState(demoAccounts[0].email);
  const [password, setPassword] = useState('demo1234');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await apiFetch<{ employee: CurrentEmployee }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      notifyIdentityChanged();
      router.replace('/');
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : '로그인하지 못했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (configurationError) return <main className="centered-state" role="alert">접속 설정을 불러오지 못했습니다. 새로고침 후 다시 확인해주세요.</main>;
  if (!configuration) return <main className="centered-state" role="status">접속 설정을 확인하고 있습니다.</main>;
  if (configuration.enabled) return (
    <DemoEntry
      durationMinutes={configuration.durationMinutes}
      expenseAiAvailable={configuration.aiCapabilities?.approvalDraft === true}
    />
  );

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="tw:mb-8"><BrandLogo inverse /></div>
        <p className="eyebrow">JHWORKS · SYNTHETIC COMPANY</p>
        <h1 className="tw:break-keep tw:max-[480px]:text-4xl! tw:max-[480px]:leading-tight!">업무 흐름은 단순하게.<br />AI 실행은 안전하게.</h1>
        <p>
          JHWorks AI Groupware는 가상 기업의 결재 흐름 위에서 AI Review, RAG, Tool Calling과
          Human-in-the-loop를 단계적으로 검증하는 독립 프로젝트입니다.
        </p>
        <div className="phase-marker">
          <span>현재 단계</span>
          <strong>경비 작성 → 확인 후 제출 → 결재자 승인</strong>
        </div>
      </section>
      <section className="login-panel">
        <div>
          <p className="eyebrow">DEMO SIGN IN</p>
          <h2>JHWorks 계정 선택</h2>
          <p className="subtle">모든 계정과 데이터는 이 프로젝트를 위해 만든 가상 정보입니다.</p>
        </div>
        <div className="account-grid">
          {demoAccounts.map((account) => (
            <button
              className={email === account.email ? 'account-option selected' : 'account-option'}
              key={account.email}
              onClick={() => setEmail(account.email)}
              type="button"
            >
              <strong>{account.label}</strong>
              <span>{account.description}</span>
            </button>
          ))}
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            <span>이메일</span>
            <input onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
          </label>
          <label>
            <span>비밀번호</span>
            <input
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          {error && <p className="error-banner">{error}</p>}
          <button className="primary-button full-width" disabled={isSubmitting} type="submit">
            {isSubmitting ? '로그인 중…' : 'Demo 로그인'}
          </button>
        </form>
      </section>
    </main>
  );
}
