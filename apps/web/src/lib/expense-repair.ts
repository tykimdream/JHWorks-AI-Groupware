import type { Approval } from '@/lib/types';

export const expenseRepairFields = ['amount', 'expenseDate', 'merchant', 'category', 'purpose'] as const;
export type ExpenseRepairField = typeof expenseRepairFields[number];
export function parseExpenseRepairField(value: string | null): ExpenseRepairField | undefined {
  return expenseRepairFields.find((field) => field === value);
}
export function repairFieldForCheck(field: string): ExpenseRepairField | undefined {
  return parseExpenseRepairField(field === 'amount' ? field : field.startsWith('details.') ? field.slice(8) : null);
}
export function latestRejectionComment(approval: Approval): string | null {
  return approval.lines.filter((line) => line.status === 'REJECTED')
    .sort((a, b) => b.round - a.round || b.step - a.step)[0]?.comment ?? null;
}
