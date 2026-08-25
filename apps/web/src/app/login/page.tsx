'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { ApiError, apiFetch } from '@/lib/api';
import type { CurrentEmployee } from '@/lib/types';

const demoAccounts = [
  {
    label: '작성자 · 윤서진',
    email: 'seojin.yoon@jhworks.test',
    description: '출장 Draft 작성과 제출',
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
      router.replace('/approvals');
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : '로그인하지 못했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-story">
        <p className="eyebrow">JHWORKS · SYNTHETIC COMPANY</p>
        <h1>업무 흐름은 단순하게.<br />AI 실행은 안전하게.</h1>
        <p>
          JHWorks AI Groupware는 가상 기업의 결재 흐름 위에서 AI Review, RAG, Tool Calling과
          Human-in-the-loop를 단계적으로 검증하는 독립 프로젝트입니다.
        </p>
        <div className="phase-marker">
          <span>현재 단계</span>
          <strong>Phase 4 · Natural-language Approval Draft</strong>
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
