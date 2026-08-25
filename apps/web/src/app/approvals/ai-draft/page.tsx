import { AppShell } from '@/components/app-shell';
import { ApprovalDraftAssistant } from '@/components/approval-draft-assistant';

export default function AIApprovalDraftPage() {
  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">PHASE 4 · AI APPROVAL DRAFT</p>
          <h1>AI로 결재 초안 만들기</h1>
          <p>업무 요청을 자연어로 말하면 빠진 정보를 확인한 뒤 회사 양식으로 정리합니다.</p>
        </div>
      </header>
      <ApprovalDraftAssistant />
    </AppShell>
  );
}
