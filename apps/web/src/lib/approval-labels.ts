import type { ApprovalType, ExpenseCategory } from '@/lib/types';

export const approvalTypeLabels: Record<ApprovalType, string> = {
  GENERAL: '일반 결재',
  BUSINESS_TRIP: '출장 신청',
  EXPENSE: '경비 정산',
  LEAVE: '휴가 신청',
};

export const expenseCategoryLabels: Record<ExpenseCategory, string> = {
  TRANSPORTATION: '교통비',
  LODGING: '숙박비',
  MEALS: '식비',
  OTHER: '기타',
};
