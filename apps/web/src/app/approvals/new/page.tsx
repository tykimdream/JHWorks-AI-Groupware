import { AppShell } from '@/components/app-shell';
import { ApprovalForm } from '@/components/approval-form';

export default function NewApprovalPage() {
  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">NEW DRAFT</p>
          <h1>결재 문서 작성</h1>
          <p>Draft는 미완성 상태로 저장할 수 있으며 제출 시 필수 항목을 검증합니다.</p>
        </div>
      </header>
      <ApprovalForm />
    </AppShell>
  );
}

