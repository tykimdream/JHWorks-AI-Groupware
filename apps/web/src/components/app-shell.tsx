'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { ReactNode } from 'react';

import { useCurrentEmployee } from '@/hooks/use-current-employee';
import { apiFetch } from '@/lib/api';

interface AppShellProps {
  children: ReactNode;
}

export const AppShell = ({ children }: AppShellProps) => {
  const router = useRouter();
  const { employee, isLoading } = useCurrentEmployee();

  const handleLogout = async () => {
    await apiFetch<{ success: boolean }>('/auth/logout', { method: 'POST' });
    router.replace('/login');
  };

  if (isLoading || !employee) {
    return <main className="centered-state">업무 공간을 불러오는 중입니다.</main>;
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
          <Link href="/assistant">AI 업무 조회</Link>
          <Link href="/approvals/ai-draft">AI 초안 작성</Link>
          <Link href="/approvals/new">새 결재 작성</Link>
        </nav>
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
      <main className="workspace">{children}</main>
    </div>
  );
};
