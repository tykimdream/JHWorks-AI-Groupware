import { AppShell } from '@/components/app-shell';
import { OrganizationOverview } from '@/components/organization-overview';

export default function OrganizationPage() {
  return (
    <AppShell>
      <header className="page-header">
        <div>
          <h1>내 조직</h1>
          <p>
            소속 부서와 직속 관리자를 확인하고 결재가 전달되는 관계를
            살펴보세요.
          </p>
        </div>
      </header>
      <OrganizationOverview />
    </AppShell>
  );
}
