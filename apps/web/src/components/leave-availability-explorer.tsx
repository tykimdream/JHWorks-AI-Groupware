'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
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
  const [startDate, setStartDate] = useState('2026-09-01');
  const [endDate, setEndDate] = useState('2026-09-30');
  const [requestedDays, setRequestedDays] = useState('2.0');
  const [result, setResult] = useState<LeaveAvailability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsLoading(true);
    const query = new URLSearchParams({
      startDate,
      endDate,
      requestedDays,
      limit: '6',
    });
    try {
      const response = await apiFetch<LeaveAvailability>(
        `/attendance/leave-availability?${query.toString()}`,
      );
      setResult(response);
    } catch (caught: unknown) {
      setResult(null);
      setError(getUserErrorMessage(caught, '휴가 가능일을 계산하지 못했습니다.'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="availability-workspace">
      <form className="availability-search" onSubmit={handleSearch}>
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
              onChange={(event) => setStartDate(event.target.value)}
              required
              type="date"
              value={startDate}
            />
          </label>
          <label>
            <span>탐색 종료일</span>
            <input
              onChange={(event) => setEndDate(event.target.value)}
              required
              type="date"
              value={endDate}
            />
          </label>
          <label>
            <span>사용할 연차</span>
            <select
              onChange={(event) => setRequestedDays(event.target.value)}
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

      {error && <p className="error-banner">{error}</p>}
      {!result && !error && (
        <div className="empty-card availability-empty">
          <strong>조건을 선택해 휴가 후보를 찾아보세요.</strong>
          <span>계산 결과는 AI 추측이 아니라 현재 휴가 계정과 등록된 업무 일정에 기반합니다.</span>
        </div>
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
        이 날짜로 휴가 Draft 작성
      </Link>
    )}
  </article>
);

const AvailabilityDayCell = ({ day }: { day: LeaveAvailabilityDay }) => {
  const hasCaution = day.reasons.some((reason) => reason.impact === 'CAUTION');
  const state = !day.isSelectable ? 'blocked' : hasCaution ? 'caution' : 'clear';
  const description = day.reasons.map((reason) => reason.message).join(' · ') || '충돌 없음';
  return (
    <div className={`availability-day ${state}`} title={description}>
      <span>{weekday(day.date)}</span>
      <strong>{Number(day.date.slice(-2))}</strong>
      <small>{state === 'blocked' ? '제외' : state === 'caution' ? '주의' : '가능'}</small>
    </div>
  );
};
