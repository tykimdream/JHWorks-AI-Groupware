'use client';

import Link from 'next/link';
import { useEffect, useRef, useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import { seoulSearchRange } from '@/lib/format';
import type {
  AttendanceOverview,
  LeaveAvailability,
  LeaveAvailabilityCandidate,
  LeaveAvailabilityDay,
} from '@/lib/types';

const statusLabels = {
  READY: '후보 계산 완료',
  NO_CANDIDATE: '후보 없음',
  INSUFFICIENT_BALANCE: '잔여 연차 부족',
  ACCOUNT_UNAVAILABLE: '휴가 계정 없음',
} as const;

const candidateLabels = {
  AVAILABLE: '신청 가능',
  CAUTION: '일정 확인 필요',
} as const;

const compactDate = (value: string) => {
  const [, month, day] = value.split('-');
  return `${Number(month)}월 ${Number(day)}일`;
};

const weekday = (value: string) =>
  new Intl.DateTimeFormat('ko-KR', { weekday: 'short', timeZone: 'Asia/Seoul' }).format(
    new Date(`${value}T00:00:00+09:00`),
  );

const draftHref = (candidate: LeaveAvailabilityCandidate) => ({
  pathname: '/approvals/new',
  query: {
    type: 'LEAVE',
    startDate: candidate.startDate,
    endDate: candidate.endDate,
    leaveUnit: candidate.requestedDays === '0.5' ? 'HALF_DAY_AM' : 'FULL_DAY',
  },
});

export const LeaveAvailabilityExplorer = () => {
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const pending = new AbortController();
    controller.current = pending;
    return () => pending.abort();
  }, []);
  const [range] = useState(() => seoulSearchRange());
  const [startDate, setStartDate] = useState(range.startDate);
  const [endDate, setEndDate] = useState(range.endDate);
  const searching = useRef(false);
  const [requestedDays, setRequestedDays] = useState('2.0');
  const [result, setResult] = useState<LeaveAvailability | null>(null);
  const [overview, setOverview] = useState<AttendanceOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (searching.current) return;
    searching.current = true;
    setResult(null);
    setOverview(null);
    setError(null);
    setIsLoading(true);
    const query = new URLSearchParams({
      startDate,
      endDate,
      requestedDays,
      limit: '6',
    });
    try {
      const [response, source] = await Promise.all([
        apiFetch<LeaveAvailability>(`/attendance/leave-availability?${query.toString()}`, {
          signal: controller.current?.signal,
        }),
        apiFetch<AttendanceOverview>(`/attendance/overview?${new URLSearchParams({ startDate, endDate })}`, {
          signal: controller.current?.signal,
        }),
      ]);
      setResult(response);
      setOverview(source);
    } catch (caught: unknown) {
      setResult(null);
      setError(getUserErrorMessage(caught, '휴가 가능일을 계산하지 못했습니다.'));
    } finally {
      searching.current = false;
      setIsLoading(false);
    }
  };

  return (
    <div className="availability-workspace">
      <form aria-busy={isLoading} className="availability-search" id="manual-leave-search" tabIndex={-1} onSubmit={handleSearch}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">DETERMINISTIC SEARCH</p>
            <h2>휴가 후보 탐색</h2>
          </div>
          <span className="subtle">최대 93일 범위에서 충돌이 적은 후보를 먼저 보여줍니다.</span>
        </div>
        <div className="availability-search-grid">
          <label>
            <span>탐색 시작일</span>
            <input
              disabled={isLoading}
              onChange={(event) => { setStartDate(event.target.value); setResult(null); setOverview(null); }}
              required
              type="date"
              value={startDate}
            />
          </label>
          <label>
            <span>탐색 종료일</span>
            <input
              disabled={isLoading}
              min={startDate}
              onChange={(event) => { setEndDate(event.target.value); setResult(null); setOverview(null); }}
              required
              type="date"
              value={endDate}
            />
          </label>
          <label>
            <span>사용할 연차</span>
            <select
              disabled={isLoading}
              onChange={(event) => { setRequestedDays(event.target.value); setResult(null); setOverview(null); }}
              value={requestedDays}
            >
              <option value="0.5">반차 0.5일</option>
              <option value="1.0">1일</option>
              <option value="2.0">2일</option>
              <option value="3.0">3일</option>
              <option value="4.0">4일</option>
              <option value="5.0">5일</option>
            </select>
          </label>
          <button className="primary-button" disabled={isLoading} type="submit">
            {isLoading ? '계산 중…' : '가능한 날짜 찾기'}
          </button>
        </div>
      </form>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {isLoading && <p role="status">현재 연차와 일정을 확인하고 있습니다.</p>}
      {!result && !error && !isLoading && (
        <div className="empty-card availability-empty">
          <strong>조건을 선택해 휴가 후보를 찾아보세요.</strong>
          <span>계산 결과는 AI 추측이 아니라 현재 휴가 계정과 등록된 업무 일정에 기반합니다.</span>
        </div>
      )}
      {overview && (
        <details className="empty-card" open>
          <summary>잔여 연차와 팀 일정 원본 확인</summary>
          {overview.leaveBalances.map((balance) => (
            <p key={balance.year}>{balance.year}년 가용 {balance.availableDays}일 / 사용 {balance.usedDays}일 / 결재 대기 {balance.pendingDays}일</p>
          ))}
          {overview.leaveBalances.length === 0 && <p>해당 연도의 휴가 계정이 없습니다.</p>}
          <h3>회사 및 부서 일정</h3>
          {overview.calendarEvents.length === 0 ? <p>이 범위에 등록된 회사 및 부서 일정이 없습니다.</p> : (
            <ul>{overview.calendarEvents.map((event) => (
              <li key={event.id}>{event.startDate} ~ {event.endDate}: {event.title} ({event.status === 'TENTATIVE' ? '잠정 일정' : event.impact === 'BLOCKED' ? '필수 일정' : event.impact === 'CAUTION' ? '주의 일정' : '참고 일정'})</li>
            ))}</ul>
          )}
          <h3>같은 팀 휴가</h3>
          {overview.teamLeaves.length === 0 ? <p>이 범위에 등록된 팀 휴가가 없습니다.</p> : (
            <ul>{overview.teamLeaves.map((leave) => (
              <li key={leave.id}>{leave.startDate} ~ {leave.endDate}: {leave.employee.name}</li>
            ))}</ul>
          )}
          <p className="subtle">현재 사용자에게 허용된 정보만 표시하며 동료의 휴가 사유는 제공하지 않습니다. 저장 및 제출 시 서버가 다시 검증합니다.</p>
        </details>
      )}
      {result && <AvailabilityResult result={result} />}
    </div>
  );
};

export const AvailabilityResult = ({
  result,
  onCandidateSelect,
  candidateActionLabel,
  candidateActionDisabled = false,
}: {
  result: LeaveAvailability;
  onCandidateSelect?: (candidate: LeaveAvailabilityCandidate) => void;
  candidateActionLabel?: string;
  candidateActionDisabled?: boolean;
}) => (
  <>
    <section className="availability-summary">
      <div>
        <span>계산 상태</span>
        <strong>{statusLabels[result.status]}</strong>
      </div>
      <div>
        <span>가용 연차</span>
        <strong>{result.leaveBalance ? `${result.leaveBalance.availableDays}일` : '-'}</strong>
      </div>
      <div>
        <span>요청 일수</span>
        <strong>{result.requestedDays}일</strong>
      </div>
      <div>
        <span>추천 후보</span>
        <strong>{result.candidates.length}개</strong>
      </div>
    </section>

    {result.reasons.length > 0 && (
      <section className="availability-notice" aria-label="후보를 만들 수 없는 이유">
        {result.reasons.map((reason) => (
          <p key={reason.code}>{reason.message}</p>
        ))}
      </section>
    )}

    {result.candidates.length > 0 && (
      <section>
        <div className="section-heading availability-section-heading">
          <div>
            <p className="eyebrow">RECOMMENDED WINDOWS</p>
            <h2>신청 후보</h2>
          </div>
          <span className="subtle">주의 후보는 팀 일정과 인수인계를 한 번 더 확인하세요.</span>
        </div>
        <div className="candidate-grid">
          {result.candidates.map((candidate) => (
            <CandidateCard
              actionLabel={candidateActionLabel}
              actionDisabled={candidateActionDisabled}
              candidate={candidate}
              key={`${candidate.startDate}-${candidate.endDate}`}
              onSelect={onCandidateSelect}
            />
          ))}
        </div>
      </section>
    )}

    <section>
      <div className="section-heading availability-section-heading">
        <div>
          <p className="eyebrow">DATE SIGNALS</p>
          <h2>날짜별 판단 근거</h2>
        </div>
        <div className="availability-legend" aria-label="날짜 상태 범례">
          <span className="clear">가능</span>
          <span className="caution">주의</span>
          <span className="blocked">제외</span>
        </div>
      </div>
      <div className="availability-calendar">
        {result.days.map((day) => <AvailabilityDayCell day={day} key={day.date} />)}
      </div>
    </section>
  </>
);

const CandidateCard = ({
  candidate,
  onSelect,
  actionLabel,
  actionDisabled,
}: {
  candidate: LeaveAvailabilityCandidate;
  onSelect?: (candidate: LeaveAvailabilityCandidate) => void;
  actionLabel?: string;
  actionDisabled?: boolean;
}) => (
  <article className={`candidate-card candidate-${candidate.status.toLowerCase()}`}>
    <div className="candidate-card-heading">
      <span>{candidateLabels[candidate.status]}</span>
      <strong>{candidate.requestedDays}일</strong>
    </div>
    <h3>
      {compactDate(candidate.startDate)} → {compactDate(candidate.endDate)}
    </h3>
    <p className="candidate-workdays">
      실제 차감일 {candidate.workDates.map(compactDate).join(', ')}
    </p>
    <ul>
      {candidate.reasons.map((reason) => (
        <li key={`${reason.code}-${reason.eventIds.join('-')}`}>{reason.message}</li>
      ))}
    </ul>
    {onSelect ? (
      <button
        className="secondary-button full-width"
        disabled={actionDisabled}
        onClick={() => onSelect(candidate)}
        type="button"
      >
        {actionLabel ?? '이 날짜로 exact preview 만들기'}
      </button>
    ) : (
      <Link className="secondary-button full-width" href={draftHref(candidate)}>
        이 날짜로 휴가 결재 작성
      </Link>
    )}
  </article>
);

const AvailabilityDayCell = ({ day }: { day: LeaveAvailabilityDay }) => {
  const hasCaution = day.reasons.some((reason) => reason.impact === 'CAUTION');
  const state = !day.isSelectable ? 'blocked' : hasCaution ? 'caution' : 'clear';
  const description = day.reasons.map((reason) => reason.message).join(' · ') || '충돌 없음';
  return (
    <div className={`availability-day ${state}`} tabIndex={0} aria-label={`${day.date}: ${description}`} title={description}>
      <span>{weekday(day.date)}</span>
      <strong>{Number(day.date.slice(-2))}</strong>
      <small>{state === 'blocked' ? '제외' : state === 'caution' ? '주의' : '가능'}</small>
    </div>
  );
};
