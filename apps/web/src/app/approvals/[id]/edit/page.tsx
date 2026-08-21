'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { AppShell } from '@/components/app-shell';
import { ApprovalForm } from '@/components/approval-form';
import { ApiError, apiFetch } from '@/lib/api';
import type { Approval } from '@/lib/types';

export default function EditApprovalPage() {
  const { id } = useParams<{ id: string }>();
  const [approval, setApproval] = useState<Approval | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Approval>(`/approvals/${id}`)
      .then(setApproval)
      .catch((caught: unknown) => {
        setError(caught instanceof ApiError ? caught.message : 'Draft를 불러오지 못했습니다.');
      });
  }, [id]);

  return (
    <AppShell>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">EDIT DRAFT</p>
          <h1>결재 문서 수정</h1>
          <p>저장 시 version을 확인해 다른 변경을 덮어쓰지 않습니다.</p>
        </div>
      </header>
      {error && <p className="error-banner">{error}</p>}
      {!approval && !error && <div className="empty-card">Draft를 불러오는 중입니다.</div>}
      {approval && <ApprovalForm initial={approval} />}
    </AppShell>
  );
}

