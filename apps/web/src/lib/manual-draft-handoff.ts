import type { ApprovalType } from '@/lib/types';

const keyFor = (employeeId: string) => `jhworks:manual-draft:${employeeId}`;
const lifetimeMs = 15 * 60_000;
export interface ManualDraftHandoff {
  content: string;
  type?: ApprovalType;
}

// Explicit, tab-local transfer only. Never put business text in a URL or long-lived storage.
export function storeManualDraft(employeeId: string, value: ManualDraftHandoff): boolean {
  if (!value.content.trim() || value.content.length > 5000) return false;
  try {
    window.sessionStorage.setItem(keyFor(employeeId), JSON.stringify({ ...value, expiresAt: Date.now() + lifetimeMs }));
    return true;
  } catch { return false; }
}

export function readManualDraft(employeeId: string): ManualDraftHandoff | null {
  try {
    const raw = window.sessionStorage.getItem(keyFor(employeeId));
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (typeof value.expiresAt !== 'number' || value.expiresAt <= Date.now() || value.expiresAt > Date.now() + lifetimeMs ||
        typeof value.content !== 'string' || value.content.length > 5000 || !value.content.trim() ||
        (value.type !== undefined && !['BUSINESS_TRIP', 'EXPENSE', 'LEAVE', 'GENERAL'].includes(value.type))) {
      clearManualDraft(employeeId);
      return null;
    }
    return { content: value.content, type: value.type };
  } catch { clearManualDraft(employeeId); return null; }
}

export function clearManualDraft(employeeId: string): void {
  try { window.sessionStorage.removeItem(keyFor(employeeId)); } catch { /* Disabled storage. */ }
}
