'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useState, type ReactNode } from 'react';

import { BrandLogo } from '@/components/brand-logo';
import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { notifyIdentityChanged } from '@/lib/session-events';
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
      notifyIdentityChanged(true);
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
      <aside className="sidebar tw:sticky tw:top-0 tw:flex tw:h-dvh tw:min-h-0 tw:flex-col tw:overflow-hidden tw:border-0 tw:border-r tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:px-4 tw:pt-7 tw:pb-4 tw:text-jhw-text tw:max-[900px]:static tw:max-[900px]:h-auto tw:max-[900px]:gap-4 tw:max-[900px]:border-r-0 tw:max-[900px]:border-b tw:max-[900px]:p-4">
        <div>
          <BrandLogo />
          <p className="workspace-label">우리의 일, 더 가볍게.</p>
        </div>
        <nav
          className="nav-list tw:min-h-0 tw:flex-1 tw:content-start tw:overflow-y-auto tw:overscroll-contain tw:max-[900px]:flex-none"
          aria-label="주 메뉴"
        >
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
          {configuration?.aiCapabilities?.workAssistant && (
            <Link href="/assistant" aria-current={pathname === '/assistant' ? 'page' : undefined}>
              <WorkspaceIcon name="search" />
              AI 업무 조회
            </Link>
          )}
          {configuration?.aiCapabilities?.approvalDraft && (
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
          <span className="nav-caption nav-caption-support">도움말</span>
          <Link href="/pattern">
            <WorkspaceIcon name="document" />
            JHW Pattern
          </Link>
          <Link href="/feedback">
            <WorkspaceIcon name="message" />
            의견 남기기
          </Link>
        </nav>
        <footer className="sidebar-footer tw:mt-4 tw:grid tw:shrink-0 tw:gap-4 tw:border-0 tw:border-t tw:border-solid tw:border-jhw-border tw:pt-4 tw:max-[900px]:mt-0 tw:max-[900px]:grid-cols-[minmax(0,1fr)_auto] tw:max-[900px]:items-center tw:max-[900px]:gap-3">
          {configuration?.enabled && (
            <>
              <p className="tw:m-0 tw:flex tw:items-center tw:gap-2 tw:text-xs tw:leading-5 tw:text-jhw-muted tw:max-[900px]:hidden">
                <span
                  className="tw:size-1.5 tw:shrink-0 tw:rounded-full tw:bg-jhw-success"
                  aria-hidden="true"
                />
                방문자 전용 체험 공간
              </p>
              <DemoRoleSwitcher key={employee.id} currentRole={employee.role} fullWidth />
            </>
          )}
          <div className="profile-card tw:flex tw:min-w-0 tw:items-center tw:gap-2 tw:max-[900px]:col-start-1 tw:max-[900px]:row-start-1">
            <div
              className="tw:grid tw:size-8 tw:shrink-0 tw:place-items-center tw:rounded-full tw:bg-jhw-primary-subtle tw:text-sm tw:font-semibold tw:text-jhw-primary"
              aria-hidden="true"
            >
              {employee.name.slice(0, 1)}
            </div>
            <div className="tw:grid tw:min-w-0 tw:flex-1 tw:gap-0.5">
              <strong className="tw:truncate tw:text-sm">{employee.name}</strong>
              <span className="tw:text-xs tw:leading-4 tw:text-jhw-muted">{employee.position}</span>
              {!configuration?.enabled && (
                <span className="tw:break-words tw:text-xs tw:leading-4 tw:text-jhw-muted tw:max-[900px]:hidden">
                  {employee.department.name}
                </span>
              )}
            </div>
            <button
              className="tw:min-h-9 tw:shrink-0 tw:cursor-pointer tw:rounded-lg tw:border-0 tw:bg-transparent tw:px-1.5 tw:text-xs tw:text-jhw-muted tw:hover:bg-jhw-canvas tw:hover:text-jhw-text tw:disabled:cursor-wait tw:disabled:opacity-50"
              disabled={isLoggingOut}
              onClick={handleLogout}
              type="button"
            >
              {isLoggingOut ? '종료 중…' : '로그아웃'}
            </button>
          </div>
        </footer>
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
