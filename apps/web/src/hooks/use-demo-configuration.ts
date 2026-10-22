'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface DemoConfiguration {
  enabled: boolean;
  durationMinutes: number;
  writeLimit: number;
  requestLimit: number;
}

export const useDemoConfiguration = () => {
  const [configuration, setConfiguration] = useState<DemoConfiguration | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<DemoConfiguration>('/demo/configuration', { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setConfiguration(value); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, []);
  return { configuration, error };
};
