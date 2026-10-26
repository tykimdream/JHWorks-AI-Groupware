import { AppShell } from '@/components/app-shell';
import { PrototypeExplorer } from '@/components/prototype-explorer';

export default function ExplorePage() {
  return (
    <AppShell>
      <header className="page-header">
        <div>
          <h1>업무 체험 안내</h1>
          <p>
            가상 회사에서 작성자와 결재자가 되어, 요청부터 처리 결과까지 직접
            경험해 보세요.
          </p>
        </div>
      </header>
      <PrototypeExplorer />
    </AppShell>
  );
}
