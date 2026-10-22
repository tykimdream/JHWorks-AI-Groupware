'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { ApiError, apiFetch } from '@/lib/api';
import type { CurrentEmployee } from '@/lib/types';

export const IDENTITY_CHANGED_EVENT = 'jhworks:identity-changed';

export const useCurrentEmployee = () => {
  const router = useRouter();
  const [employee, setEmployee] = useState<CurrentEmployee | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    let controller: AbortController | null = null;
    let active = true;
    const refresh = () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      setIsRefreshing(true);
      apiFetch<CurrentEmployee>('/employees/me', { signal })
        .then((current) => { if (active && !signal.aborted) setEmployee(current); })
        .catch((error: unknown) => {
          if (!active || signal.aborted) return;
          setEmployee(null);
          if (error instanceof ApiError && error.status === 401) router.replace('/login');
        })
        .finally(() => {
          if (active && !signal.aborted) {
            setIsLoading(false);
            setIsRefreshing(false);
          }
        });
    };
    refresh();
    window.addEventListener('focus', refresh);
    window.addEventListener(IDENTITY_CHANGED_EVENT, refresh);
    return () => {
      active = false;
      controller?.abort();
      window.removeEventListener('focus', refresh);
      window.removeEventListener(IDENTITY_CHANGED_EVENT, refresh);
    };
  }, [router]);

  return { employee, isLoading, isRefreshing };
};

