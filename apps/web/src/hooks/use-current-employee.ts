'use client';

import { useQuery } from '@tanstack/react-query';

import { useSessionScope } from '@/components/session-data-provider';
import { apiFetch } from '@/lib/api';
import type { CurrentEmployee } from '@/lib/types';

export { IDENTITY_CHANGED_EVENT } from '@/lib/session-events';

export const useCurrentEmployee = () => {
  const { epoch, guest } = useSessionScope();
  const query = useQuery({
    queryKey: ['session', epoch, 'employee'],
    queryFn: ({ signal }) => apiFetch<CurrentEmployee>('/employees/me', { signal }),
    enabled: !guest,
  });
  return {
    employee: query.isError ? null : query.data ?? null,
    isLoading: query.isPending,
    isRefreshing: query.isFetching && !query.isPending,
  };
};
