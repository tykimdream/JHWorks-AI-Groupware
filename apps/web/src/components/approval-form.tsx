'use client';

import { useRouter } from 'next/navigation';
import { useMemo, useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
  Approval,
  ApprovalDraftInput,
  ApprovalType,
  BusinessTripDetails,
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

const numberOrNull = (value: string): number | null => (value === '' ? null : Number(value));

export const ApprovalForm = ({ initial }: ApprovalFormProps) => {
  const router = useRouter();
  const initialTrip = initial?.details.kind === 'BUSINESS_TRIP' ? initial.details : blankTripDetails;
  const [type, setType] = useState<ApprovalType>(initial?.type ?? 'BUSINESS_TRIP');
  const [title, setTitle] = useState(initial?.title ?? '');
  const [content, setContent] = useState(initial?.content ?? '');
  const [amount, setAmount] = useState(initial?.amount?.toString() ?? '');
  const [destination, setDestination] = useState(initialTrip.destination ?? '');
  const [startDate, setStartDate] = useState(initialTrip.startDate ?? '');
  const [endDate, setEndDate] = useState(initialTrip.endDate ?? '');
  const [clientName, setClientName] = useState(initialTrip.clientName ?? '');
  const [visitPurpose, setVisitPurpose] = useState(initialTrip.visitPurpose ?? '');
  const [transportation, setTransportation] = useState(
    initialTrip.costBreakdown?.transportation?.toString() ?? '',
  );
  const [lodging, setLodging] = useState(initialTrip.costBreakdown?.lodging?.toString() ?? '');
  const [meals, setMeals] = useState(initialTrip.costBreakdown?.meals?.toString() ?? '');
  const [other, setOther] = useState(initialTrip.costBreakdown?.other?.toString() ?? '');
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const breakdownTotal = useMemo(
    () => [transportation, lodging, meals, other].reduce((sum, value) => sum + Number(value || 0), 0),
    [transportation, lodging, meals, other],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSaving(true);

    const details: ApprovalDraftInput['details'] =
      type === 'GENERAL'
        ? { kind: 'GENERAL' }
        : {
            kind: 'BUSINESS_TRIP',
            destination: destination || null,
            startDate: startDate || null,
            endDate: endDate || null,
            clientName: clientName || null,
            visitPurpose: visitPurpose || null,
            costBreakdown: {
              transportation: numberOrNull(transportation),
              lodging: numberOrNull(lodging),
              meals: numberOrNull(meals),
              other: numberOrNull(other),
            },
          };

    const payload: ApprovalDraftInput = {
      type,
      title,
      content,
      amount: numberOrNull(amount),
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
            <option value="GENERAL">일반 결재</option>
          </select>
        </label>
        <label>
          <span>예상 금액 (원)</span>
          <input min="0" onChange={(event) => setAmount(event.target.value)} type="number" value={amount} />
        </label>
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
              <input onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} />
            </label>
            <label>
              <span>종료일</span>
              <input onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} />
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
