export const formatCurrency = (amount: number | null): string => {
  if (amount === null) {
    return '금액 없음';
  }
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(amount);
};

export const formatDate = (value: string | null): string => {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium' }).format(new Date(value));
};

