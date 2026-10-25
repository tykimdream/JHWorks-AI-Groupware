import type { ApprovalType, ExpenseDetails, LeaveUnit } from '@/lib/types';

const prefix = 'jhworks:approval-form:';
const lifetime = 15 * 60_000;
const limit = 32_000;
export const textFields = ['title', 'content', 'amount', 'destination', 'tripStartDate', 'tripEndDate',
  'clientName', 'visitPurpose', 'transportation', 'lodging', 'meals', 'other',
  'leaveStartDate', 'leaveEndDate', 'leaveReason', 'handoverNote'] as const;
export type ApprovalFormValues = Record<typeof textFields[number], string> & {
  type: ApprovalType; leaveUnit: LeaveUnit; expense: ExpenseDetails;
};
export const recoveryKey = (employeeId: string, documentId: string) => `${prefix}${employeeId}:${documentId}`;

function validValues(value: unknown): value is ApprovalFormValues {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  if (Object.keys(v).length !== textFields.length + 3 || !textFields.every((key) => typeof v[key] === 'string' && v[key].length <= 5000)) return false;
  if (typeof v.type !== 'string' || !['GENERAL', 'EXPENSE', 'BUSINESS_TRIP', 'LEAVE'].includes(v.type)
    || typeof v.leaveUnit !== 'string' || !['FULL_DAY', 'HALF_DAY_AM', 'HALF_DAY_PM'].includes(v.leaveUnit)) return false;
  if (!v.expense || typeof v.expense !== 'object') return false;
  const expense = v.expense as Record<string, unknown>;
  return Object.keys(expense).length === 6 && expense.kind === 'EXPENSE'
    && ['expenseDate', 'merchant', 'purpose', 'receiptReference'].every((key) => expense[key] === null || (typeof expense[key] === 'string' && expense[key].length <= 5000))
    && [null, 'TRANSPORTATION', 'LODGING', 'MEALS', 'OTHER'].includes(expense.category as string | null);
}

export function readFormRecovery(key: string, version: number | null): ApprovalFormValues | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    if (raw.length > limit) throw new Error('oversized');
    const entry = JSON.parse(raw);
    if (entry.schema !== 1 || entry.version !== version || !Number.isFinite(entry.expiresAt)
      || entry.expiresAt <= Date.now() || entry.expiresAt > Date.now() + lifetime || !validValues(entry.values)) throw new Error('invalid');
    return entry.values;
  } catch { clearFormRecovery(key); return null; }
}

export function storeFormRecovery(key: string, version: number | null, values: ApprovalFormValues): boolean {
  try {
    if (!validValues(values)) { clearFormRecovery(key); return false; }
    const raw = JSON.stringify({ schema: 1, version, expiresAt: Date.now() + lifetime, values });
    if (raw.length > limit) { clearFormRecovery(key); return false; }
    sessionStorage.setItem(key, raw);
    return true;
  } catch { clearFormRecovery(key); return false; }
}

export function clearFormRecovery(key: string) {
  try { sessionStorage.removeItem(key); } catch { /* Storage may be disabled. */ }
}

export function clearEmployeeFormRecovery(employeeId: string) {
  try {
    const keys = Object.keys(sessionStorage).filter((key) => key.startsWith(`${prefix}${employeeId}:`));
    keys.forEach(clearFormRecovery);
  } catch { /* Storage may be disabled. */ }
}
