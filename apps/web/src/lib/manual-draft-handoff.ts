import type { ApprovalType, ExpenseDetails } from '@/lib/types';

const keyFor = (employeeId: string) => `jhworks:manual-draft:${employeeId}`;
const lifetimeMs = 15 * 60_000;
export interface ManualDraftHandoff {
  content: string;
  type?: ApprovalType;
  expensePreset?: {
    title: string;
    amount: number;
    details: ExpenseDetails;
  };
}

function valid(value: ManualDraftHandoff): boolean {
  if (
    typeof value.content !== 'string' ||
    !value.content.trim() ||
    value.content.length > 5000 ||
    (value.type !== undefined &&
      !['BUSINESS_TRIP', 'EXPENSE', 'LEAVE', 'GENERAL'].includes(value.type))
  )
    return false;
  if (value.expensePreset !== undefined) {
    const preset = value.expensePreset;
    if (
      !preset ||
      value.type !== 'EXPENSE' ||
      typeof preset.title !== 'string' ||
      !preset.title.trim() ||
      preset.title.length > 120 ||
      !Number.isSafeInteger(preset.amount) ||
      preset.amount <= 0 ||
      preset.amount > 1_000_000_000
    )
      return false;
    const details = preset.details;
    if (
      !details ||
      details.kind !== 'EXPENSE' ||
      typeof details.expenseDate !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(details.expenseDate) ||
      Number.isNaN(Date.parse(`${details.expenseDate}T00:00:00Z`)) ||
      new Date(`${details.expenseDate}T00:00:00Z`)
        .toISOString()
        .slice(0, 10) !== details.expenseDate ||
      !['TRANSPORTATION', 'LODGING', 'MEALS', 'OTHER'].includes(
        details.category ?? '',
      )
    )
      return false;
    for (const field of [details.merchant, details.purpose]) {
      if (typeof field !== 'string' || !field.trim() || field.length > 200)
        return false;
    }
    if (
      details.receiptReference !== null &&
      (typeof details.receiptReference !== 'string' ||
        details.receiptReference.length > 200)
    )
      return false;
  }
  return true;
}

// Explicit, tab-local transfer only. Never put business text in a URL or long-lived storage.
// These are unsaved input values, never proof of authorization or server validation.
export function storeManualDraft(
  employeeId: string,
  value: ManualDraftHandoff,
): boolean {
  if (!valid(value)) return false;
  try {
    window.sessionStorage.setItem(
      keyFor(employeeId),
      JSON.stringify({ ...value, expiresAt: Date.now() + lifetimeMs }),
    );
    return true;
  } catch {
    return false;
  }
}

export function readManualDraft(employeeId: string): ManualDraftHandoff | null {
  try {
    const raw = window.sessionStorage.getItem(keyFor(employeeId));
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (
      !value ||
      typeof value.expiresAt !== 'number' ||
      value.expiresAt <= Date.now() ||
      value.expiresAt > Date.now() + lifetimeMs ||
      !valid(value)
    ) {
      clearManualDraft(employeeId);
      return null;
    }
    return {
      content: value.content,
      type: value.type,
      expensePreset: value.expensePreset,
    };
  } catch {
    clearManualDraft(employeeId);
    return null;
  }
}

export function clearManualDraft(employeeId: string): void {
  try {
    window.sessionStorage.removeItem(keyFor(employeeId));
  } catch {
    /* Disabled storage. */
  }
}
