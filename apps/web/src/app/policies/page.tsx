import { AppShell } from '@/components/app-shell';
import { PolicyLibrary } from '@/components/policy-library';

export default function PoliciesPage() {
  return (
    <AppShell>
      <header className="page-header">
        <div>
          <h1>회사 규정</h1>
          <p>
            출장·경비·휴가 규정을 원문과 버전으로 확인하고, 필요한 업무로
            이어가세요.
          </p>
        </div>
      </header>
      <PolicyLibrary />
    </AppShell>
  );
}
