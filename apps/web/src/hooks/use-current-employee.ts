'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { ApiError, apiFetch } from '@/lib/api';
import type { CurrentEmployee } from '@/lib/types';

export const useCurrentEmployee = () => {
  const router = useRouter();
  const [employee, setEmployee] = useState<CurrentEmployee | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    apiFetch<CurrentEmployee>('/employees/me')
      .then(setEmployee)
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          router.replace('/login');
          return;
        }
        setEmployee(null);
      })
      .finally(() => setIsLoading(false));
  }, [router]);

  return { employee, isLoading };
};

