import type { ExpenseDetails } from '@/lib/types';
import { expenseCategoryLabels } from '@/lib/approval-labels';
import { formatCurrency } from '@/lib/format';

export function ExpenseSummary({
  expense,
  amount,
}: {
  expense: ExpenseDetails;
  amount: number | null;
}) {
  return (
    <section className="expense-summary">
      <p className="eyebrow">EXPENSE SETTLEMENT</p>
      <h2>지출 내역</h2>
      <dl className="detail-grid">
        <div>
          <dt>실제 지출일</dt>
          <dd>{expense.expenseDate || '미입력'}</dd>
        </div>
        <div>
          <dt>사용처</dt>
          <dd>{expense.merchant || '미입력'}</dd>
        </div>
        <div>
          <dt>비용 구분</dt>
          <dd>{expense.category ? expenseCategoryLabels[expense.category] : '미입력'}</dd>
        </div>
        <div>
          <dt>정산 금액</dt>
          <dd>{formatCurrency(amount)}</dd>
        </div>
        <div className="wide">
          <dt>업무 목적</dt>
          <dd>{expense.purpose || '미입력'}</dd>
        </div>
        <div className="wide">
          <dt>증빙 참조</dt>
          <dd>{expense.receiptReference || '등록된 참조 없음'}</dd>
        </div>
      </dl>
      <p className="expense-evidence-note">
        증빙 참조는 원본 문서를 찾기 위한 정보입니다. 파일 업로드·원본 검증은 지원하지 않으며,
        결재자는 영수증 원본을 별도로 확인해야 합니다.
      </p>
    </section>
  );
}
