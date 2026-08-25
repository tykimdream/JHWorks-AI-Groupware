import { AppShell } from '@/components/app-shell';
import { ApprovalForm, type ApprovalFormPreset } from '@/components/approval-form';

interface NewApprovalPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function NewApprovalPage({ searchParams }: NewApprovalPageProps) {
  const query = await searchParams;
  const startDate = typeof query.startDate === 'string' ? query.startDate : null;
  const endDate = typeof query.endDate === 'string' ? query.endDate : null;
  const leaveUnit = query.leaveUnit;
  const preset: ApprovalFormPreset | undefined =
    query.type === 'LEAVE' &&
    startDate !== null &&
    endDate !== null &&
    (leaveUnit === 'FULL_DAY' || leaveUnit === 'HALF_DAY_AM' || leaveUnit === 'HALF_DAY_PM')
      ? { type: 'LEAVE', startDate, endDate, leaveUnit }
      : undefined;

  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">NEW DRAFT</p>
          <h1>결재 문서 작성</h1>
          <p>Draft는 미완성 상태로 저장할 수 있으며 제출 시 필수 항목을 검증합니다.</p>
        </div>
      </header>
      <ApprovalForm preset={preset} />
    </AppShell>
  );
}
