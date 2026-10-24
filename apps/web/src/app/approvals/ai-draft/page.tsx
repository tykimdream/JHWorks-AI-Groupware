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
      <p className="draft-support-note">
        출장 신청·경비 정산·일반 결재를 지원합니다. 지출 내역과 규정 근거를 확인한 뒤 저장해 주세요.
      </p>
      <ApprovalDraftAssistant />
    </AppShell>
  );
}
