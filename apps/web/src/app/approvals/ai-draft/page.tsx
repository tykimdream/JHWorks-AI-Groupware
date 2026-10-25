import { AICapabilityGate } from '@/components/ai-capability-gate';
import { AppShell } from '@/components/app-shell';
import { ApprovalDraftAssistant } from '@/components/approval-draft-assistant';

export default function AIApprovalDraftPage() {
  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">AI DRAFT STUDIO</p>
          <h1>말하면, 결재의 시작이 됩니다.</h1>
          <p>업무 요청을 자연어로 말하면 빠진 정보를 확인한 뒤 회사 양식으로 정리합니다.</p>
        </div>
      </header>
      <AICapabilityGate capability="approvalDraft">
        <ApprovalDraftAssistant />
      </AICapabilityGate>
    </AppShell>
  );
}
