import { AppShell } from '@/components/app-shell';
import { LeaveAvailabilityExplorer } from '@/components/leave-availability-explorer';
import { LeaveAssistant } from '@/components/leave-assistant';

export default function AttendancePage() {
  return (
    <AppShell>
      <header className="page-header">
        <div>
          <p className="eyebrow">ATTENDANCE &amp; LEAVE</p>
          <h1>근태·휴가</h1>
          <p>잔여 연차와 회사·프로젝트·팀 일정을 함께 확인해 신청할 날짜를 찾습니다.</p>
        </div>
      </header>
      <LeaveAssistant />
      <LeaveAvailabilityExplorer />
    </AppShell>
  );
}
