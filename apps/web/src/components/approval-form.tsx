'use client';

import { Alert, Field, Input, Select, Textarea } from '@jhworks/pattern/react';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type {
  Approval,
  ApprovalDraftInput,
  ApprovalType,
  BusinessTripDetails,
  LeaveDetails,
  LeaveUnit,
  ExpenseDetails,
  ExpenseCategory,
} from '@/lib/types';
import { useWorkspaceEmployee } from '@/components/app-shell';
import { clearManualDraft, readManualDraft } from '@/lib/manual-draft-handoff';
import { ExpenseWorkGuide } from '@/components/expense-work-guide';
import { ConfirmationDialog } from '@/components/confirmation-dialog';
import { useNavigationGuard } from '@/components/navigation-guard';
import { clearFormRecovery, readFormRecovery, recoveryKey, storeFormRecovery, type ApprovalFormValues } from '@/lib/approval-form-recovery';
import { expenseCategoryLabels } from '@/lib/approval-labels';
import { getSessionGeneration } from '@/lib/session-events';
import type { ExpenseRepairField } from '@/lib/expense-repair';

interface ApprovalFormProps {
  initial?: Approval;
  initialType?: ApprovalType;
  manualHandoff?: boolean;
  listScope?: 'mine' | 'assigned';
  focusField?: ExpenseRepairField;
  preset?: ApprovalFormPreset;
}

export interface ApprovalFormPreset {
  type: 'LEAVE';
  startDate: string;
  endDate: string;
  leaveUnit: LeaveUnit;
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

export const ApprovalForm = ({ initial, preset, initialType, manualHandoff = false, listScope, focusField }: ApprovalFormProps) => {
  const router = useRouter();
  const employee = useWorkspaceEmployee();
  const [handoff] = useState(() => !initial && manualHandoff && employee ? readManualDraft(employee.id) : null);
  useEffect(() => {
    if (!initial && manualHandoff && employee) clearManualDraft(employee.id);
  }, [employee, initial, manualHandoff]);
  const initialTrip =
    initial?.details.kind === 'BUSINESS_TRIP' ? initial.details : blankTripDetails;
  const initialLeave =
    initial?.details.kind === 'LEAVE'
      ? initial.details
      : {
          ...blankLeaveDetails,
          startDate: preset?.startDate ?? '',
          endDate: preset?.endDate ?? '',
          leaveUnit: preset?.leaveUnit ?? 'FULL_DAY',
        };
  const [type, setType] = useState<ApprovalType>(initial?.type ?? preset?.type ?? handoff?.type ?? initialType ?? 'BUSINESS_TRIP');
  const [expense, setExpense] = useState<ExpenseDetails>(
    initial?.details.kind === 'EXPENSE'
      ? initial.details
      : handoff?.expensePreset?.details ?? {
          kind: 'EXPENSE',
          expenseDate: '',
          merchant: '',
          category: null,
          purpose: '',
          receiptReference: '',
        },
  );
  const [title, setTitle] = useState(
    initial?.title ?? handoff?.expensePreset?.title ?? (preset ? `${preset.startDate} 휴가 신청` : ''),
  );
  const [content, setContent] = useState(
    initial?.content ?? handoff?.content ?? (preset ? '업무 일정과 인수인계를 확인한 후 연차 사용을 신청합니다.' : ''),
  );
  const [amount, setAmount] = useState(initial?.amount?.toString() ?? handoff?.expensePreset?.amount.toString() ?? '');
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

  const values: ApprovalFormValues = { type, expense, title, content, amount, destination, tripStartDate, tripEndDate, clientName, visitPurpose, transportation, lodging, meals, other, leaveUnit, leaveStartDate, leaveEndDate, leaveReason, handoverNote };
  const serialized = JSON.stringify(values);
  const [baseline] = useState(serialized);
  const dirty = baseline !== serialized;
  const key = employee ? recoveryKey(employee.id, initial?.id ?? 'new') : null;
  const [recovery, setRecovery] = useState(() => key ? readFormRecovery(key, initial?.version ?? null) : null);
  const [storageFailed, setStorageFailed] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<(() => void) | null>(null);
  const navigationGuardRef = useNavigationGuard();
  const saved = useRef(false);
  const saving = useRef(false);
  const hadChanges = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const focusedRepair = useRef(false);
  useEffect(() => {
    if (!focusField || recovery || type !== 'EXPENSE' || focusedRepair.current) return;
    const field = document.getElementById(`expense-field-${focusField}`);
    if (!field) return;
    focusedRepair.current = true;
    field.focus({ preventScroll: true });
    field.scrollIntoView({ block: 'center', behavior: 'instant' });
  }, [focusField, recovery, type]);

  useEffect(() => {
    if (!key || saved.current) return;
    if (!dirty) { if (hadChanges.current) clearFormRecovery(key); return; }
    hadChanges.current = true;
    // Browser storage availability is only known after the write side effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStorageFailed(!storeFormRecovery(key, initial?.version ?? null, JSON.parse(serialized)));
  }, [key, dirty, serialized, initial?.version]);

  useEffect(() => {
    if (!dirty) return;
    const guard = (navigate: () => void) => {
      if (saved.current) navigate();
      else setPendingNavigation(() => navigate);
    };
    navigationGuardRef.current = guard;
    const warn = (event: BeforeUnloadEvent) => {
      if (saved.current) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => {
      if (navigationGuardRef.current === guard) navigationGuardRef.current = null;
      window.removeEventListener('beforeunload', warn);
    };
  }, [dirty, navigationGuardRef]);

  const restore = () => {
    if (!recovery) return;
    setType(recovery.type);
    setExpense(recovery.expense);
    setTitle(recovery.title);
    setContent(recovery.content);
    setAmount(recovery.amount);
    setDestination(recovery.destination);
    setTripStartDate(recovery.tripStartDate);
    setTripEndDate(recovery.tripEndDate);
    setClientName(recovery.clientName);
    setVisitPurpose(recovery.visitPurpose);
    setTransportation(recovery.transportation);
    setLodging(recovery.lodging);
    setMeals(recovery.meals);
    setOther(recovery.other);
    setLeaveUnit(recovery.leaveUnit);
    setLeaveStartDate(recovery.leaveStartDate);
    setLeaveEndDate(recovery.leaveEndDate);
    setLeaveReason(recovery.leaveReason);
    setHandoverNote(recovery.handoverNote);
    setRecovery(null);
  };
  const cancelEditing = () => {
    const navigate = () => router.push(initial ? `/approvals/${initial.id}${listScope ? `?from=${listScope}` : ''}` : '/approvals');
    if (dirty) setPendingNavigation(() => navigate);
    else navigate();
  };

  const breakdownTotal = useMemo(
    () =>
      [transportation, lodging, meals, other].reduce((sum, value) => sum + Number(value || 0), 0),
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
    if (saving.current) return;
    const requestGeneration = getSessionGeneration();
    saving.current = true;
    setError(null);
    setIsSaving(true);

    let details: ApprovalDraftInput['details'];
    if (type === 'GENERAL') {
      details = { kind: 'GENERAL' };
    } else if (type === 'EXPENSE') {
      details = { ...expense, expenseDate: expense.expenseDate || null };
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
      const approval = await apiFetch<Approval>(
        initial ? `/approvals/${initial.id}` : '/approvals',
        {
          method: initial ? 'PATCH' : 'POST',
          body: JSON.stringify(payload),
        },
      );
      if (requestGeneration !== getSessionGeneration()) return;
      saved.current = true;
      if (key) clearFormRecovery(key);
      if (mounted.current) router.push(`/approvals/${approval.id}${listScope ? `?from=${listScope}` : ''}`);
    } catch (caught: unknown) {
      setError(getUserErrorMessage(caught, '초안을 저장하지 못했습니다.'));
    } finally {
      saving.current = false;
      setIsSaving(false);
    }
  };

  return (
    <form className="document-form" onSubmit={handleSubmit} aria-busy={isSaving} onChange={() => { if (recovery) setRecovery(null); }}>
      <ConfirmationDialog open={pendingNavigation !== null} title="저장하지 않고 이동할까요?" description="변경한 내용과 이 탭의 임시 입력을 지우고 이동합니다. 저장하려면 계속 작성을 선택해주세요." confirmLabel="저장하지 않고 이동" cancelLabel="계속 작성" onCancel={() => setPendingNavigation(null)} onConfirm={() => {
        const navigate = pendingNavigation;
        if (!navigate || saving.current) return;
        saved.current = true;
        if (key) clearFormRecovery(key);
        setPendingNavigation(null);
        navigate();
      }} busy={isSaving} />
      {recovery && !dirty && <section className="form-guidance" aria-label="이전 입력 복원">
        <p>이 탭에 저장하지 않은 입력이 있습니다. 이어서 작성할까요? 새로 입력하면 이전 임시 입력을 대체합니다.</p>
        <div className="button-row">
          <button type="button" className="secondary-button" onClick={restore}>이전 입력 이어쓰기</button>
          <button type="button" className="text-button" onClick={() => { if (key) clearFormRecovery(key); setRecovery(null); }}>이전 입력 지우기</button>
        </div>
      </section>}
      {dirty && <p className="form-guidance" role="status">{storageFailed
        ? '이 브라우저에서는 입력을 임시 보관하지 못했습니다. 화면을 떠나기 전에 초안으로 저장해주세요.'
        : '입력을 이 탭에 최대 15분 임시 보관합니다. 서버에 저장하려면 초안 저장을 눌러주세요.'}</p>}

      {type === 'EXPENSE' && <ExpenseWorkGuide approval={initial?.type === 'EXPENSE' ? initial : undefined} onFocusField={(field) => {
        const name = field === 'amount' ? field : field.replace('details.', '');
        const target = document.getElementById(`expense-field-${name}`);
        target?.focus({ preventScroll: true });
        target?.scrollIntoView({ block: 'center', behavior: 'instant' });
      }} />}
      <fieldset disabled={isSaving} className="tw:contents">
      {manualHandoff && <p role="status" className="form-guidance">{handoff
        ? handoff.expensePreset
          ? '예시 체험에서 확인한 정보를 옮겼습니다. 내용을 수정하고 초안 저장을 눌러주세요. 아직 저장되지 않았습니다.'
          : 'AI 화면의 요청과 추가 답변을 업무 내용으로 옮겼습니다. 문서 유형과 실제 지출 정보를 직접 확인해주세요. 아직 저장되지 않았습니다.'
        : '이어받을 입력이 없거나 15분 보관 시간이 지났습니다. 직접 내용을 입력해주세요.'}</p>}
      <div className="form-section form-grid-two">
        <label>
          <span>결재 종류</span>
          <select value={type} onChange={(event) => setType(event.target.value as ApprovalType)}>
            <option value="BUSINESS_TRIP">출장 신청</option>
            <option value="EXPENSE">경비 정산</option>
            <option value="LEAVE">휴가 신청</option>
            <option value="GENERAL">일반 결재</option>
          </select>
        </label>
        {type !== 'LEAVE' && (
          <Field id="expense-field-amount" label={type === 'EXPENSE' ? '실제 지출 금액 (원)' : '예상 금액 (원)'}>
            <Input
              inputMode="numeric"
              onChange={(event) => setAmount(event.target.value.replace(/[^0-9]/g, ''))}
              type="text"
              value={amount.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
            />
          </Field>
        )}
      </div>

      <div className="form-section">
        <Field label="제목" required>
          <Input
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </Field>
        <Field label="업무 내용">
          <Textarea
            maxLength={5000}
            onChange={(event) => setContent(event.target.value)}
            placeholder="결재자가 목적과 기대 결과를 이해할 수 있도록 작성하세요."
            rows={6}
            value={content}
          />
        </Field>
      </div>

      {type === 'EXPENSE' && (
        <section className="form-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">EXPENSE SETTLEMENT</p>
              <h2>경비 정산 정보</h2>
            </div>
            <span className="subtle">이미 지출한 비용을 기록합니다.</span>
          </div>
          <div className="form-grid-two">
            <Field id="expense-field-expenseDate" label="실제 지출일">
              <Input
                type="date"
                value={expense.expenseDate ?? ''}
                onChange={(event) => setExpense({ ...expense, expenseDate: event.target.value })}
              />
            </Field>
            <Field id="expense-field-merchant" label="사용처">
              <Input
                maxLength={200}
                placeholder="예: 코레일"
                value={expense.merchant ?? ''}
                onChange={(event) => setExpense({ ...expense, merchant: event.target.value })}
              />
            </Field>
            <Field id="expense-field-category" label="비용 구분">
              <Select
                value={expense.category ?? ''}
                onChange={(event) =>
                  setExpense({
                    ...expense,
                    category: event.target.value ? (event.target.value as ExpenseCategory) : null,
                  })
                }
              >
                <option value="">선택해 주세요</option>
                {Object.entries(expenseCategoryLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="expense-field-receiptReference" label="증빙 참조 (선택)">
              <Input
                maxLength={255}
                placeholder="예: 사내 문서번호 RCP-CES-001"
                value={expense.receiptReference ?? ''}
                onChange={(event) =>
                  setExpense({ ...expense, receiptReference: event.target.value })
                }
              />
            </Field>
          </div>
          <Field id="expense-field-purpose" label="업무상 지출 목적">
            <Textarea
              rows={3}
              maxLength={1000}
              value={expense.purpose ?? ''}
              onChange={(event) => setExpense({ ...expense, purpose: event.target.value })}
            />
          </Field>
          <p className="expense-evidence-note">
            증빙 참조만 기록하며 파일을 업로드하지 않습니다. 영수증 원본은 결재자가 별도로 확인해야
            합니다.
          </p>
        </section>
      )}

      {type === 'BUSINESS_TRIP' && (
        <div className="form-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">STRUCTURED DATA</p>
              <h2>출장 정보</h2>
            </div>
            <span className="subtle">비어 있는 항목도 초안으로 저장할 수 있습니다.</span>
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
              <input
                onChange={(event) => setTripStartDate(event.target.value)}
                type="date"
                value={tripStartDate}
              />
            </label>
            <label>
              <span>종료일</span>
              <input
                onChange={(event) => setTripEndDate(event.target.value)}
                type="date"
                value={tripEndDate}
              />
            </label>
          </div>
          <label>
            <span>방문 목적</span>
            <textarea
              onChange={(event) => setVisitPurpose(event.target.value)}
              rows={3}
              value={visitPurpose}
            />
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
                  inputMode="numeric"
                  onChange={(event) => (setter as (next: string) => void)(event.target.value.replace(/[^0-9]/g, ''))}
                  type="text"
                  value={(value as string).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                />
              </label>
            ))}
          </div>
          <p className="calculated-total">
            세부 비용 합계: {breakdownTotal.toLocaleString('ko-KR')}원
          </p>
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
                value={
                  estimatedLeaveDays === null ? '날짜를 선택해주세요' : `${estimatedLeaveDays}일`
                }
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

      {error && <Alert tone="danger">{error}</Alert>}
      <div className="sticky-actions">
        <button className="secondary-button" disabled={isSaving} onClick={cancelEditing} type="button">
          취소
        </button>
        <button className="primary-button" disabled={isSaving} type="submit">
          {isSaving ? '저장 중…' : '초안 저장'}
        </button>
      </div>
      </fieldset>
    </form>
  );
};
