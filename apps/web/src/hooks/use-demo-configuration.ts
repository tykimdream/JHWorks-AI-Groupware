'use client';

import { useQuery } from '@tanstack/react-query';
import { useSessionScope } from '@/components/session-data-provider';
import { apiFetch } from '@/lib/api';

export type AICapability =
  | 'approvalDraft'
  | 'approvalReview'
  | 'leaveAssistant'
  | 'workAssistant'
  | 'policyEmbedding';

interface DemoConfiguration {
  aiCapabilities: Record<AICapability, boolean>;
  expenseAiRequestLimit?: number | null;
  enabled: boolean;
  durationMinutes: number;
  writeLimit: number;
  requestLimit: number;
}

export const useDemoConfiguration = () => {
  const { epoch } = useSessionScope();
  const query = useQuery({
    queryKey: ['session', epoch, 'configuration'],
    queryFn: ({ signal }) => apiFetch<DemoConfiguration>('/demo/configuration', { signal }),
  });
  return { configuration: query.isError ? null : query.data ?? null, error: query.isError };
};
