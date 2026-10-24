'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useState, type ReactNode } from 'react';

import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { DemoRoleSwitcher } from '@/components/demo-entry';
import { apiFetch } from '@/lib/api';
import { clearDraftRequest } from '@/lib/draft-handoff';
import type { CurrentEmployee } from '@/lib/types';
import { WorkspaceIcon, type WorkspaceIconName } from '@/components/workspace-icon';

const EmployeeContext = createContext<CurrentEmployee | null>(null);
export const useWorkspaceEmployee = () => useContext(EmployeeContext);

const navigation: { href: string; label: string; icon: WorkspaceIconName }[] = [
  { href: '/', label: '업무 홈', icon: 'home' },
  { href: '/approvals', label: '전자결재', icon: 'document' },
  { href: '/attendance', label: '근태·휴가', icon: 'calendar' },
];

interface AppShellProps {
  children: ReactNode;
}

export const AppShell = ({ children }: AppShellProps) => {
  const router = useRouter();
  const pathname = usePathname();
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
      if (employee) clearDraftRequest(employee.id);
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
    return (
      <main className="centered-state" role="alert">
        계정 정보를 확인하지 못했습니다. <Link href="/login">다시 로그인</Link> ·{' '}
        <Link href="/feedback">의견 남기기</Link>
      </main>
    );
  }

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div>
          <Link className="brand" href="/">
            <span className="brand-mark">j.</span> JHWorks
          </Link>
          <p className="workspace-label">우리의 일, 더 가볍게.</p>
        </div>
        <nav className="nav-list" aria-label="주 메뉴">
          <span className="nav-caption">WORKSPACE</span>
          {navigation.map(({ href, label, icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={
                (
                  href === '/'
                    ? pathname === '/'
                    : pathname.startsWith(href) && pathname !== '/approvals/ai-draft'
                )
                  ? 'page'
                  : undefined
              }
            >
              <WorkspaceIcon name={icon} />
              {label}
            </Link>
          ))}
          {!configuration?.enabled && (
            <Link href="/assistant" aria-current={pathname === '/assistant' ? 'page' : undefined}>
              <WorkspaceIcon name="search" />
              AI 업무 조회
            </Link>
          )}
          {!configuration?.enabled && (
            <Link
              href="/approvals/ai-draft"
              aria-current={pathname === '/approvals/ai-draft' ? 'page' : undefined}
            >
              <WorkspaceIcon name="sparkles" />
              AI 초안 작성
            </Link>
          )}
          <Link href="/approvals/new">
            <WorkspaceIcon name="plus" />새 결재 작성
          </Link>
          <span className="nav-caption nav-caption-support">FEEDBACK</span>
          <Link href="/feedback">
            <WorkspaceIcon name="message" />
            의견 남기기
          </Link>
        </nav>
        <div className="sidebar-note">
          <span className="online-dot" />
          합성 데이터 체험 공간
          <p>
            직접 작성하고, 검토하고,
            <br />
            업무의 흐름을 경험해 보세요.
          </p>
        </div>
        {configuration?.enabled && (
          <DemoRoleSwitcher key={employee.id} currentRole={employee.role} />
        )}
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
        <div className="workspace-topbar">
          <span>
            내 워크스페이스 <span className="breadcrumb-divider">/</span>{' '}
            {pathname === '/'
              ? '업무 홈'
              : pathname.startsWith('/approvals')
                ? '전자결재'
                : pathname.startsWith('/attendance')
                  ? '근태·휴가'
                  : '업무 도구'}
          </span>
          <span className="environment-badge">
            <span className="online-dot" />
            DEMO WORKSPACE
          </span>
        </div>
        {logoutError && (
          <p role="alert" className="error-banner">
            로그아웃하지 못했습니다. 다시 시도해주세요.
          </p>
        )}
        {(isRefreshing || isLoggingOut) && <p role="status">계정 상태를 확인하고 있습니다.</p>}
        <EmployeeContext.Provider value={employee}>
          <div
            key={`${employee.id}-${employee.role}-${employee.departmentId}-${employee.manager?.id ?? 'none'}`}
            hidden={isRefreshing || isLoggingOut}
          >
            {children}
          </div>
        </EmployeeContext.Provider>
      </main>
    </div>
  );
};
