import { ContextHint } from '@/components/context-hint';
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
          <p>작성 중인 문서는 초안으로 저장됩니다. 저장 후 내용을 확인하고 별도로 제출하세요.</p>
        </div>
      </header>
      <p className="form-guidance">아직 정보가 부족해도 저장할 수 있어요. <ContextHint label="초안과 제출의 차이">초안은 나만 수정할 수 있고, 제출하면 지정 결재자에게 전달됩니다.</ContextHint></p>
      <ApprovalForm manualHandoff={query.handoff === 'manual'} preset={preset} initialType={query.type === 'EXPENSE' ? 'EXPENSE' : undefined} />
    </AppShell>
  );
}
