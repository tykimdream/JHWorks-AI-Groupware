'use client';

import Link from 'next/link';
import { useRef, useState, type FormEvent } from 'react';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { ApiError, apiFetch, getUserErrorMessage } from '@/lib/api';
import { notifyIdentityChanged } from '@/lib/session-events';

export default function FeedbackPage() {
  const { configuration, error: configurationError } = useDemoConfiguration();
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState('usability');
  const [screen, setScreen] = useState('general');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [needsVisit, setNeedsVisit] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true;
    setBusy(true); setError(null); setNotice(null);
    try {
      const result = await apiFetch<{ id: string }>('/demo/feedback', {
        method: 'POST', body: JSON.stringify({ category, screen, message, consent }),
      });
      setReceipt(result.id);
    } catch (caught: unknown) {
      if (caught instanceof ApiError && caught.status === 401) {
        setNeedsVisit(true);
        setError('체험 연결이 없거나 만료됐습니다. 입력한 의견은 유지됩니다. 아래에서 체험을 연결한 뒤 다시 보내주세요.');
      } else if (caught instanceof ApiError && caught.status === 422) {
        setError('의견은 공백을 제외해 10자 이상 입력하고, 이메일·인증정보를 제외해주세요.');
      } else {
        setError(getUserErrorMessage(caught, '전송하지 못했습니다. 의견은 유지되니 다시 시도해주세요.'));
      }
    } finally { pending.current = false; setBusy(false); }
  };
  const connect = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(null);
    try {
      await apiFetch('/demo/start', { method: 'POST' });
      notifyIdentityChanged();
      setNeedsVisit(false); setNotice('체험이 연결됐습니다. 작성한 의견을 보내주세요.');
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '체험을 연결하지 못했습니다. 잠시 후 다시 시도해주세요.'));
    } finally { pending.current = false; setBusy(false); }
  };

  return (
    <main className="feedback-page">
      <header className="page-header">
        <div><p className="eyebrow">JHWORKS · FEEDBACK</p><h1>써보니 어떠셨나요?</h1>
          <p>불편한 점이나 개선 아이디어를 남겨주세요. 접수한 의견은 개발자가 직접 검토합니다.</p></div>
      </header>
      <nav className="button-row" aria-label="돌아가기">
        <Link href="/approvals">데모로 돌아가기</Link><a href="https://pikan.dev/ko">포트폴리오</a>
      </nav>
      {configurationError ? <p role="alert" className="error-banner">접수 상태를 불러오지 못했습니다. 새로고침 후 다시 확인해주세요.</p>
        : !configuration ? <p role="status">접수 상태를 확인하고 있습니다.</p>
          : !configuration.enabled ? <p role="status" className="form-section">피드백 접수를 준비 중입니다. 공개 데모가 열리면 이곳에서 의견을 남길 수 있습니다.</p>
            : receipt ? <section className="form-section" role="status">
              <h2>의견을 접수했습니다</h2><p>검토 후 필요한 내용을 개선에 반영하겠습니다. 개별 답변은 제공하지 않습니다.</p>
              <p>접수 번호: <code>{receipt}</code></p>
            </section> : <form className="form-section feedback-form" onSubmit={submit} aria-busy={busy}>
              <div className="form-grid-two">
                <label><span>의견 종류</span><select value={category} onChange={(e) => setCategory(e.target.value)} disabled={busy}>
                  <option value="usability">사용하기 불편해요</option><option value="bug">오류가 있어요</option><option value="idea">아이디어가 있어요</option>
                </select></label>
                <label><span>어느 화면인가요?</span><select value={screen} onChange={(e) => setScreen(e.target.value)} disabled={busy}>
                  <option value="general">전체·기타</option><option value="approvals">전자결재</option><option value="attendance">근태·휴가</option><option value="assistant">AI 기능</option>
                </select></label>
              </div>
              <label htmlFor="feedback-message">의견</label>
              <textarea id="feedback-message" value={message} onChange={(e) => setMessage(e.target.value)}
                minLength={10} maxLength={1000} required rows={7} disabled={busy}
                aria-describedby="feedback-help feedback-length"
                placeholder="어떤 작업 중 무엇이 불편했는지, 기대한 동작은 무엇인지 알려주세요." />
              <p id="feedback-length" className="subtle">{message.length} / 1,000자 · 10자 이상</p>
              <p id="feedback-help" className="subtle">이름·이메일·전화번호·회사 정보·비밀번호·인증 키를 입력하지 마세요. 파일은 받지 않습니다. 의견은 공개되지 않습니다.</p>
              <label className="feedback-consent"><input type="checkbox" required checked={consent}
                onChange={(e) => setConsent(e.target.checked)} disabled={busy} />
                <span>개선 검토 목적으로 의견을 비공개로 최대 30일 보관하는 데 동의합니다. 개별 답변은 받지 않습니다.</span></label>
              {error && <p role="alert" className="error-banner">{error}</p>}
              {notice && <p role="status">{notice}</p>}
              <div className="button-row">
                {needsVisit && <button type="button" className="secondary-button" onClick={connect} disabled={busy}>체험 연결하기</button>}
                <button type="submit" className="primary-button" disabled={busy || !consent || message.trim().length < 10}>
                  {busy ? '처리 중…' : '의견 보내기'}</button>
              </div>
              <p className="subtle">체험 공간당 1회 접수합니다. 전송 결과가 불확실하면 같은 내용으로 다시 보내도 중복 접수되지 않습니다.</p>
            </form>}
    </main>
  );
}
