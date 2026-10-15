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
  return new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeZone: 'Asia/Seoul' }).format(new Date(value));
};


// Calendar dates use Seoul regardless of the browser's timezone.
export const seoulSearchRange = (now = new Date()) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const part = (type: string) => parts.find((item) => item.type === type)!.value;
  const startDate = `${part('year')}-${part('month')}-${part('day')}`;
  const end = new Date(`${startDate}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() + 30);
  const yearEnd = `${part('year')}-12-31`;
  return { startDate, endDate: [end.toISOString().slice(0, 10), yearEnd].sort()[0] };
};
