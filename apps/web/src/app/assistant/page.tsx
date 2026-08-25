import { AppShell } from '@/components/app-shell';
import { WorkAssistant } from '@/components/work-assistant';

export default function WorkAssistantPage() {
  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">PHASE 5 · ENTERPRISE TOOL CALLING</p>
          <h1>AI 업무 조회</h1>
          <p>현재 사용자 권한 안에서 조직·결재·정책 데이터를 안전하게 조회합니다.</p>
        </div>
      </header>
      <WorkAssistant />
    </AppShell>
  );
}
