'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type FormEvent } from 'react';

import { useWorkspaceEmployee } from '@/components/app-shell';
import { StatusBadge } from '@/components/status-badge';
import { WorkspaceIcon } from '@/components/workspace-icon';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { formatDate } from '@/lib/format';
import type { ApprovalListResponse } from '@/lib/types';
import { approvalTypeLabels } from '@/lib/approval-labels';
import { ExpenseInsightPanel } from '@/components/expense-checks';
import { storeDraftRequest } from '@/lib/draft-handoff';

const examples = [
  { label: 'CES 경비 정산', request: '이번 CES 출장에서 쓴 17만원 경비 정산 결재를 준비해줘.' },
  {
    label: '출장 결재 준비',
    request:
      '다음 주 화요일 부산에서 열리는 CES 협력사 미팅 출장 신청을 준비해줘. 예상 교통비는 17만원이야.',
  },
  {
    label: '업무 협조 요청',
    request:
      'CES 참가 준비를 위해 디자인팀에 전시 부스 제작 협조를 요청하는 일반 결재 초안을 만들어줘.',
  },
];

export function WorkHome() {
  const employee = useWorkspaceEmployee();
  const router = useRouter();
  const { configuration } = useDemoConfiguration();
  const [request, setRequest] = useState('');
  const [handoffError, setHandoffError] = useState(false);
  const [data, setData] = useState<{
    mine: ApprovalListResponse;
    assigned: ApprovalListResponse;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);
  const aiAvailable = configuration !== null && !configuration.enabled;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiFetch<ApprovalListResponse>('/approvals?scope=mine', { signal: controller.signal }),
      apiFetch<ApprovalListResponse>('/approvals?scope=assigned', { signal: controller.signal }),
    ])
      .then(([mine, assigned]) => {
        if (!controller.signal.aborted) {
          setData({ mine, assigned });
          setError(null);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(getUserErrorMessage(caught, '업무 현황을 불러오지 못했습니다.'));
      });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'j' && aiAvailable) {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [aiAvailable]);

  const startDraft = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (aiAvailable && request.trim() && employee) {
      if (!storeDraftRequest(employee.id, request.trim())) {
        setHandoffError(true);
        return;
      }
      setHandoffError(false);
      router.push('/approvals/ai-draft');
    }
  };
  const drafts = data?.mine.items.filter((item) => item.status === 'DRAFT') ?? [];
  const pending = data?.assigned.items.filter((item) => item.status === 'PENDING') ?? [];
  const rejected = data?.mine.items.filter((item) => item.status === 'REJECTED') ?? [];
  const recent = [...(data?.mine.items ?? [])]
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .slice(0, 4);
  const nextDocument = pending[0] ?? rejected[0] ?? drafts[0];
  const date = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date());

  return (
    <div className="work-home">
      <header className="home-heading">
        <div>
          <p className="home-date">
            {date} <span>오늘의 워크스페이스</span>
          </p>
          <h1>
            {employee?.name ?? ''}님, 좋은 하루 보내세요<span className="greeting-dot">.</span>
          </h1>
          <p>반복되는 일은 가볍게, 중요한 일에 더 집중하세요.</p>
        </div>
        <Link className="secondary-button" href="/approvals/new">
          <WorkspaceIcon name="plus" size={17} />
          직접 작성
        </Link>
      </header>

      <section className="home-ai-card" aria-labelledby="home-ai-title">
        <div className="ai-card-intro">
          <span className="ai-symbol">
            <WorkspaceIcon name="sparkles" size={23} />
          </span>
          <span>
            JHWorks AI <span className="small-pill">업무 도우미</span>
          </span>
          <span className="ai-card-note">제출은 언제나 내가 확인한 후에</span>
        </div>
        <h2 id="home-ai-title">{configuration?.enabled ? '직접 작성하고 결재 흐름을 체험하세요' : '어떤 업무를 도와드릴까요?'}</h2>
        <p>{configuration?.enabled
          ? '공개 체험에서는 AI 호출이 꺼져 있습니다. 경비를 직접 작성한 뒤 사전 확인·제출·승인을 경험해 보세요.'
          : '필요한 일을 말해 주세요. 빠진 정보를 함께 확인하고 결재 초안을 준비할게요.'}</p>
        <form onSubmit={startDraft} className="home-composer">
          <label className="sr-only" htmlFor="home-request">
            AI 업무 요청
          </label>
          <textarea
            id="home-request"
            ref={input}
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            maxLength={2000}
            rows={2}
            disabled={!aiAvailable}
            placeholder={
              configuration?.enabled
                ? '현재 공개 체험에서는 AI 호출이 비활성화되어 있습니다.'
                : '예: 다음 주 부산 고객사 미팅 출장 결재를 준비해줘. 교통비는 17만 원이야.'
            }
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <div className="composer-footer">
            <span>
              <WorkspaceIcon name="document" size={15} />
              출장 신청 · 경비 정산 · 일반 결재{' '}
              <span className="composer-shortcut">⌘ / Ctrl + Enter</span>
            </span>
            <button
              type="submit"
              className="composer-send"
              aria-label="AI 초안 작성으로 이동"
              disabled={!aiAvailable || !request.trim()}
            >
              <WorkspaceIcon name="arrow" size={20} />
            </button>
          </div>
        </form>
        {handoffError && (
          <p className="error-banner" role="alert">
            요청을 전달하지 못했습니다. 입력 내용은 유지됩니다. 내용을 복사한 뒤{' '}
            <Link href="/approvals/ai-draft">초안 화면에서 직접 입력해 주세요.</Link>
          </p>
        )}
        <div className="home-examples">
          <span>이렇게 시작해 보세요</span>
          {examples.map((example) => (
            <button
              key={example.label}
              type="button"
              disabled={!aiAvailable}
              onClick={() => {
                setRequest(example.request);
                input.current?.focus();
              }}
            >
              <WorkspaceIcon name="plus" size={13} />
              {example.label}
            </button>
          ))}
          <Link href="/attendance">
            휴가 날짜 찾기 <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </section>

      {error && (
        <div className="home-error" role="alert">
          <p>{error}</p>
          <button className="text-button" onClick={() => setAttempt((value) => value + 1)}>
            다시 불러오기
          </button>
        </div>
      )}
      <section className="home-stats" aria-label="내 결재 현황" aria-busy={!data && !error}>
        {[
          {
            title: '내가 처리할 결재',
            count: data ? pending.length : null,
            icon: 'document' as const,
            tone: 'violet',
            note: '내 검토가 필요한 문서',
          },
          {
            title: '결재 진행 중',
            count: data ? data.mine.items.filter((item) => item.status === 'PENDING').length : null,
            icon: 'clock' as const,
            tone: 'amber',
            note: '결재자의 응답을 기다려요',
          },
          {
            title: '이어서 작성할 문서',
            count: data ? drafts.length : null,
            icon: 'document' as const,
            tone: 'blue',
            note: '아직 제출하지 않은 초안',
          },
          {
            title: '결재 완료',
            count: data
              ? data.mine.items.filter((item) => item.status === 'APPROVED').length
              : null,
            icon: 'check' as const,
            tone: 'green',
            note: '승인이 완료된 내 문서',
          },
        ].map((stat) => (
          <Link
            href={stat.title === '내가 처리할 결재' ? '/approvals?scope=assigned' : '/approvals'}
            className="home-stat"
            key={stat.title}
          >
            <div>
              <span>{stat.title}</span>
              <span className={`stat-icon ${stat.tone}`}>
                <WorkspaceIcon name={stat.icon} size={17} />
              </span>
            </div>
            <strong>
              {stat.count ?? '—'}
              <small>건</small>
            </strong>
            <p>{stat.note}</p>
          </Link>
        ))}
      </section>

      <ExpenseInsightPanel />
      <div className="home-bottom-grid">
        <section className="home-panel">
          <div className="panel-heading">
            <h2>
              최근 내 문서 <span className="count-pill">{data?.mine.total ?? '—'}</span>
            </h2>
            <Link href="/approvals">
              전체 보기 <span aria-hidden="true">↗</span>
            </Link>
          </div>
          <div className="home-document-labels">
            <span>문서명</span>
            <span>상태 / 수정일</span>
          </div>
          {!data && !error && (
            <p className="home-empty" role="status">
              문서를 불러오는 중입니다.
            </p>
          )}
          {error && !data && (
            <p className="home-empty">현황을 불러온 후 문서를 확인할 수 있습니다.</p>
          )}
          {data && recent.length === 0 && (
            <div className="home-empty">
              <WorkspaceIcon name="document" size={28} />
              <strong>첫 번째 업무를 시작해 볼까요?</strong>
              <p>{configuration?.enabled ? '경비·출장·일반·휴가 결재를 직접 작성해 보세요.' : 'AI로 초안을 준비하거나 직접 결재를 작성해 보세요.'}</p>
              <Link href="/approvals/new">새 결재 작성 →</Link>
            </div>
          )}
          {recent.map((item) => (
            <Link key={item.id} href={`/approvals/${item.id}`} className="home-document">
              <span className={`document-symbol ${item.type === 'LEAVE' ? 'green' : 'blue'}`}>
                <WorkspaceIcon name={item.type === 'LEAVE' ? 'calendar' : 'document'} size={19} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <span>
                  {approvalTypeLabels[item.type]} · {item.author.name}
                </span>
              </div>
              <div>
                <StatusBadge status={item.status} />
                <span>{formatDate(item.updatedAt)}</span>
              </div>
            </Link>
          ))}
        </section>

        <aside className="home-panel next-action-panel">
          <div className="panel-heading">
            <h2>
              <WorkspaceIcon name="sparkles" size={18} />
              다음 할 일
            </h2>
            <span className="small-pill">내 문서 기준</span>
          </div>
          {data ? (
            <>
              <span className="action-kicker">
                {pending.length
                  ? '검토를 기다리고 있어요'
                  : rejected.length
                    ? '수정이 필요한 문서가 있어요'
                    : drafts.length
                      ? '시작한 업무를 마무리해요'
                      : '업무를 시작할 준비가 됐어요'}
              </span>
              <h3>{nextDocument?.title ?? (configuration?.enabled ? '첫 경비 정산을 작성해 보세요.' : '복잡한 결재, 한 문장으로 시작하세요.')}</h3>
              <p>
                {pending.length
                  ? '내용과 첨부 자료를 검토하고 승인 또는 반려할 수 있습니다.'
                  : rejected.length
                    ? '반려 사유를 확인하고 내용을 보완해 다시 제출하세요.'
                    : drafts.length
                      ? '저장한 초안을 검토하고 필요한 정보를 채워 제출하세요.'
                      : configuration?.enabled
                        ? '지출일·사용처·금액을 입력하고 제출 전 누락과 중복 후보를 확인하세요.'
                        : '출장 목적과 일정을 알려주시면 회사 양식에 맞는 초안을 준비합니다.'}
              </p>
              <Link
                className="next-action-link"
                href={
                  nextDocument
                    ? `/approvals/${nextDocument.id}`
                    : aiAvailable
                      ? '/approvals/ai-draft'
                      : '/approvals/new'
                }
              >
                {nextDocument ? '문서 확인하기' : '결재 시작하기'}
                <WorkspaceIcon name="arrow" size={17} />
              </Link>
            </>
          ) : (
            <p className="home-empty">
              {error ? '업무 현황을 다시 불러와 주세요.' : '내 문서를 확인하고 있습니다.'}
            </p>
          )}
          <div className="home-tip">
            <span className="tip-symbol">↳</span>
            <p>
              <strong>알고 계셨나요?</strong>{configuration?.enabled
                ? '초안 저장과 제출은 별도 단계입니다. 제출 후 결재자로 역할을 전환해 승인할 수 있습니다.'
                : 'AI 초안은 확인 후 저장되며, 저장만으로 결재가 제출되지는 않습니다.'}
            </p>
          </div>
        </aside>
      </div>
      <footer className="home-footer">
        <span>작은 업무부터, 더 나은 흐름으로.</span>
        <span>JHWorks · AI Groupware</span>
      </footer>
    </div>
  );
}
