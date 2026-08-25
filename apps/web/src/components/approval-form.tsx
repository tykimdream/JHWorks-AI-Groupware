'use client';

import { useRouter } from 'next/navigation';
import { useMemo, useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
  Approval,
  ApprovalDraftInput,
  ApprovalType,
  BusinessTripDetails,
  LeaveDetails,
  LeaveUnit,
} from '@/lib/types';

interface ApprovalFormProps {
  initial?: Approval;
}

const blankTripDetails: BusinessTripDetails = {
  kind: 'BUSINESS_TRIP',
  destination: '',
  startDate: '',
  endDate: '',
  costBreakdown: {
    transportation: null,
    lodging: null,
    meals: null,
    other: null,
  },
  clientName: '',
  visitPurpose: '',
};

const blankLeaveDetails: LeaveDetails = {
  kind: 'LEAVE',
  leaveType: 'ANNUAL',
  leaveUnit: 'FULL_DAY',
  startDate: '',
  endDate: '',
  requestedDays: null,
  reason: '',
  handoverNote: '',
};

const numberOrNull = (value: string): number | null => (value === '' ? null : Number(value));

export const ApprovalForm = ({ initial }: ApprovalFormProps) => {
  const router = useRouter();
  const initialTrip = initial?.details.kind === 'BUSINESS_TRIP' ? initial.details : blankTripDetails;
  const initialLeave = initial?.details.kind === 'LEAVE' ? initial.details : blankLeaveDetails;
  const [type, setType] = useState<ApprovalType>(initial?.type ?? 'BUSINESS_TRIP');
  const [title, setTitle] = useState(initial?.title ?? '');
  const [content, setContent] = useState(initial?.content ?? '');
  const [amount, setAmount] = useState(initial?.amount?.toString() ?? '');
  const [destination, setDestination] = useState(initialTrip.destination ?? '');
  const [tripStartDate, setTripStartDate] = useState(initialTrip.startDate ?? '');
  const [tripEndDate, setTripEndDate] = useState(initialTrip.endDate ?? '');
  const [clientName, setClientName] = useState(initialTrip.clientName ?? '');
  const [visitPurpose, setVisitPurpose] = useState(initialTrip.visitPurpose ?? '');
  const [transportation, setTransportation] = useState(
    initialTrip.costBreakdown?.transportation?.toString() ?? '',
  );
  const [lodging, setLodging] = useState(initialTrip.costBreakdown?.lodging?.toString() ?? '');
  const [meals, setMeals] = useState(initialTrip.costBreakdown?.meals?.toString() ?? '');
  const [other, setOther] = useState(initialTrip.costBreakdown?.other?.toString() ?? '');
  const [leaveUnit, setLeaveUnit] = useState<LeaveUnit>(initialLeave.leaveUnit);
  const [leaveStartDate, setLeaveStartDate] = useState(initialLeave.startDate ?? '');
  const [leaveEndDate, setLeaveEndDate] = useState(initialLeave.endDate ?? '');
  const [leaveReason, setLeaveReason] = useState(initialLeave.reason ?? '');
  const [handoverNote, setHandoverNote] = useState(initialLeave.handoverNote ?? '');
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const breakdownTotal = useMemo(
    () => [transportation, lodging, meals, other].reduce((sum, value) => sum + Number(value || 0), 0),
    [transportation, lodging, meals, other],
  );

  const estimatedLeaveDays = useMemo(() => {
    if (!leaveStartDate || !leaveEndDate) {
      return null;
    }
    const start = new Date(`${leaveStartDate}T00:00:00`);
    const end = new Date(`${leaveEndDate}T00:00:00`);
    if (start > end || (leaveUnit !== 'FULL_DAY' && leaveStartDate !== leaveEndDate)) {
      return null;
    }
    if (leaveUnit !== 'FULL_DAY') {
      return start.getDay() === 0 || start.getDay() === 6 ? null : 0.5;
    }
    let weekdays = 0;
    for (const current = new Date(start); current <= end; current.setDate(current.getDate() + 1)) {
      if (current.getDay() !== 0 && current.getDay() !== 6) {
        weekdays += 1;
      }
    }
    return weekdays || null;
  }, [leaveEndDate, leaveStartDate, leaveUnit]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSaving(true);

    let details: ApprovalDraftInput['details'];
    if (type === 'GENERAL') {
      details = { kind: 'GENERAL' };
    } else if (type === 'LEAVE') {
      details = {
        kind: 'LEAVE',
        leaveType: 'ANNUAL',
        leaveUnit,
        startDate: leaveStartDate || null,
        endDate: leaveEndDate || null,
        requestedDays: null,
        reason: leaveReason || null,
        handoverNote: handoverNote || null,
      };
    } else {
      details = {
            kind: 'BUSINESS_TRIP',
            destination: destination || null,
            startDate: tripStartDate || null,
            endDate: tripEndDate || null,
            clientName: clientName || null,
            visitPurpose: visitPurpose || null,
            costBreakdown: {
              transportation: numberOrNull(transportation),
              lodging: numberOrNull(lodging),
              meals: numberOrNull(meals),
              other: numberOrNull(other),
            },
          };
    }

    const payload: ApprovalDraftInput = {
      type,
      title,
      content,
      amount: type === 'LEAVE' ? null : numberOrNull(amount),
      details,
      attachmentMetadata: initial?.attachmentMetadata ?? [],
      ...(initial ? { version: initial.version } : {}),
    };

    try {
      const approval = await apiFetch<Approval>(initial ? `/approvals/${initial.id}` : '/approvals', {
        method: initial ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      });
      router.push(`/approvals/${approval.id}`);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, 'Draft를 저장하지 못했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className="document-form" onSubmit={handleSubmit}>
      <div className="form-section form-grid-two">
        <label>
          <span>결재 종류</span>
          <select value={type} onChange={(event) => setType(event.target.value as ApprovalType)}>
            <option value="BUSINESS_TRIP">출장 신청</option>
            <option value="LEAVE">휴가 신청</option>
            <option value="GENERAL">일반 결재</option>
          </select>
        </label>
        {type !== 'LEAVE' && (
          <label>
            <span>예상 금액 (원)</span>
            <input min="0" onChange={(event) => setAmount(event.target.value)} type="number" value={amount} />
          </label>
        )}
      </div>

      <div className="form-section">
        <label>
          <span>제목</span>
          <input maxLength={120} onChange={(event) => setTitle(event.target.value)} required value={title} />
        </label>
        <label>
          <span>업무 내용</span>
          <textarea
            maxLength={5000}
            onChange={(event) => setContent(event.target.value)}
            placeholder="결재자가 목적과 기대 결과를 이해할 수 있도록 작성하세요."
            rows={6}
            value={content}
          />
        </label>
      </div>

      {type === 'BUSINESS_TRIP' && (
        <div className="form-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">STRUCTURED DATA</p>
              <h2>출장 정보</h2>
            </div>
            <span className="subtle">비어 있는 항목도 Draft로 저장할 수 있습니다.</span>
          </div>
          <div className="form-grid-two">
            <label>
              <span>출장지</span>
              <input onChange={(event) => setDestination(event.target.value)} value={destination} />
            </label>
            <label>
              <span>고객사</span>
              <input onChange={(event) => setClientName(event.target.value)} value={clientName} />
            </label>
            <label>
              <span>시작일</span>
              <input onChange={(event) => setTripStartDate(event.target.value)} type="date" value={tripStartDate} />
            </label>
            <label>
              <span>종료일</span>
              <input onChange={(event) => setTripEndDate(event.target.value)} type="date" value={tripEndDate} />
            </label>
          </div>
          <label>
            <span>방문 목적</span>
            <textarea onChange={(event) => setVisitPurpose(event.target.value)} rows={3} value={visitPurpose} />
          </label>
          <div className="cost-grid">
            {[
              ['교통비', transportation, setTransportation],
              ['숙박비', lodging, setLodging],
              ['식비', meals, setMeals],
              ['기타', other, setOther],
            ].map(([label, value, setter]) => (
              <label key={label as string}>
                <span>{label as string}</span>
                <input
                  min="0"
                  onChange={(event) => (setter as (next: string) => void)(event.target.value)}
                  type="number"
                  value={value as string}
                />
              </label>
            ))}
          </div>
          <p className="calculated-total">세부 비용 합계: {breakdownTotal.toLocaleString('ko-KR')}원</p>
        </div>
      )}

      {type === 'LEAVE' && (
        <div className="form-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">LEAVE REQUEST</p>
              <h2>휴가 정보</h2>
            </div>
            <span className="subtle">주말과 회사 휴무일을 제외해 서버가 일수를 확정합니다.</span>
          </div>
          <div className="form-grid-two">
            <label>
              <span>휴가 단위</span>
              <select
                onChange={(event) => setLeaveUnit(event.target.value as LeaveUnit)}
                value={leaveUnit}
              >
                <option value="FULL_DAY">종일 연차</option>
                <option value="HALF_DAY_AM">오전 반차</option>
                <option value="HALF_DAY_PM">오후 반차</option>
              </select>
            </label>
            <label>
              <span>예상 차감 일수</span>
              <input
                aria-label="예상 차감 일수"
                readOnly
                value={estimatedLeaveDays === null ? '날짜를 선택해주세요' : `${estimatedLeaveDays}일`}
              />
            </label>
            <label>
              <span>시작일</span>
              <input
                onChange={(event) => setLeaveStartDate(event.target.value)}
                type="date"
                value={leaveStartDate}
              />
            </label>
            <label>
              <span>종료일</span>
              <input
                onChange={(event) => setLeaveEndDate(event.target.value)}
                type="date"
                value={leaveEndDate}
              />
            </label>
          </div>
          <label>
            <span>휴가 사유 (선택)</span>
            <textarea
              maxLength={1000}
              onChange={(event) => setLeaveReason(event.target.value)}
              placeholder="공개 범위를 고려해 필요한 내용만 작성하세요."
              rows={3}
              value={leaveReason}
            />
          </label>
          <label>
            <span>인수인계 메모 (선택)</span>
            <textarea
              maxLength={2000}
              onChange={(event) => setHandoverNote(event.target.value)}
              placeholder="담당 업무와 대체 담당자 등 결재자에게 필요한 내용을 적어주세요."
              rows={3}
              value={handoverNote}
            />
          </label>
        </div>
      )}

      {error && <p className="error-banner">{error}</p>}
      <div className="sticky-actions">
        <button className="secondary-button" onClick={() => router.back()} type="button">
          취소
        </button>
        <button className="primary-button" disabled={isSaving} type="submit">
          {isSaving ? '저장 중…' : 'Draft 저장'}
        </button>
      </div>
    </form>
  );
};
