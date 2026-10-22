'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type ReactNode } from 'react';

import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { DemoRoleSwitcher } from '@/components/demo-entry';
import { apiFetch } from '@/lib/api';

interface AppShellProps {
  children: ReactNode;
}

export const AppShell = ({ children }: AppShellProps) => {
  const router = useRouter();
  const { employee, isLoading, isRefreshing } = useCurrentEmployee();
  const { configuration } = useDemoConfiguration();

  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const handleLogout = async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    setLogoutError(false);
    try {
      await apiFetch<{ success: boolean }>('/auth/logout', { method: 'POST' });
      router.replace('/login');
    } catch {
      setLogoutError(true);
      setIsLoggingOut(false);
    }
  };

  if (isLoading) {
    return <main className="centered-state">업무 공간을 불러오는 중입니다.</main>;
  }

  if (!employee) {
    return <main className="centered-state" role="alert">계정 정보를 확인하지 못했습니다. <Link href="/login">다시 로그인</Link> · <Link href="/feedback">의견 남기기</Link></main>;
  }

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div>
          <Link className="brand" href="/approvals">
            JHWorks <span>AI Groupware</span>
          </Link>
          <p className="eyebrow">JHWORKS · DEMO</p>
        </div>
        <nav className="nav-list" aria-label="주 메뉴">
          <Link href="/approvals">전자결재</Link>
          <Link href="/attendance">근태·휴가</Link>
          {!configuration?.enabled && <Link href="/assistant">AI 업무 조회</Link>}
          {!configuration?.enabled && <Link href="/approvals/ai-draft">AI 초안 작성</Link>}
          <Link href="/approvals/new">새 결재 작성</Link>
          <Link href="/feedback">의견 남기기</Link>
        </nav>
        {configuration?.enabled && <DemoRoleSwitcher key={employee.id} currentRole={employee.role} />}
        <div className="profile-card">
          <div className="avatar" aria-hidden="true">
            {employee.name.slice(0, 1)}
          </div>
          <div>
            <strong>{employee.name}</strong>
            <span>{employee.position}</span>
            <span>{employee.department.name}</span>
          </div>
          <button className="text-button" onClick={handleLogout} type="button">
            로그아웃
          </button>
        </div>
      </aside>
      <main className="workspace">
        {logoutError && <p role="alert" className="error-banner">로그아웃하지 못했습니다. 다시 시도해주세요.</p>}
        {(isRefreshing || isLoggingOut) && <p role="status">계정 상태를 확인하고 있습니다.</p>}
        <div key={`${employee.id}-${employee.role}-${employee.departmentId}-${employee.manager?.id ?? "none"}`} hidden={isRefreshing || isLoggingOut}>{children}</div>
      </main>
    </div>
  );
};
