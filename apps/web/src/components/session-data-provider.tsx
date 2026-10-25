'use client';

import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, Fragment, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import {
  advanceSessionGeneration,
  getSessionGeneration,
  IDENTITY_CHANGED_EVENT,
  notifyIdentityChanged,
  SESSION_EXPIRED_EVENT,
} from '@/lib/session-events';
import type { CurrentEmployee } from '@/lib/types';

interface SessionScope {
  epoch: number;
  guest: boolean;
}

const SessionScopeContext = createContext<SessionScope | null>(null);

export const useSessionScope = () => {
  const scope = useContext(SessionScopeContext);
  if (!scope) throw new Error('SessionDataProvider is required');
  return scope;
};

function createSessionCache() {
  let fingerprint: string | null = null;
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
      mutations: { retry: false },
    },
    queryCache: new QueryCache({
      onSuccess: (data, query) => {
        if (query.queryKey[2] !== 'employee' || query.queryKey[1] !== getSessionGeneration()) return;
        const employee = data as CurrentEmployee;
        const next = JSON.stringify([employee.id, employee.role, employee.departmentId, employee.manager?.id]);
        // Detect a cookie/account change from another tab during focus revalidation.
        // Reset the whole page state so parent page effects also lose the previous identity.
        if (fingerprint !== null && fingerprint !== next) {
          notifyIdentityChanged();
        } else {
          fingerprint = next;
        }
      },
    }),
  });
  return { client, clearFingerprint: () => { fingerprint = null; } };
}

export const SessionDataProvider = ({ children }: { children: ReactNode }) => {
  const router = useRouter();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  useEffect(() => { pathnameRef.current = pathname; }, [pathname]);
  const [scope, setScope] = useState<SessionScope>(() => ({ epoch: getSessionGeneration(), guest: false }));
  const scopeRef = useRef(scope);
  // Instance-local cache: never share server or persisted employee data.
  const [cache] = useState(createSessionCache);
  const client = cache.client;

  useEffect(() => {
    const reset = (guest: boolean) => {
      if (guest && scopeRef.current.guest) return;
      const next = { epoch: advanceSessionGeneration(), guest };
      scopeRef.current = next;
      cache.clearFingerprint();
      void client.cancelQueries();
      client.clear();
      setScope(next);
    };
    const changed = (event: Event) => {
      reset(event instanceof CustomEvent && event.detail?.guest === true);
    };
    const expired = (event: Event) => {
      if (!(event instanceof CustomEvent) || event.detail?.generation !== getSessionGeneration()) return;
      reset(true);
      // Public feedback has its own expired-visit recovery; keep its form in memory.
      if (pathnameRef.current !== '/feedback') router.replace('/login');
    };
    const refresh = () => {
      const queryKey = ['session', getSessionGeneration()];
      void client.invalidateQueries({ queryKey, refetchType: 'none' });
      // focus + visibilitychange can arrive together; retain one in-flight request.
      void client.refetchQueries({ queryKey, type: 'active' }, { cancelRefetch: false });
    };
    const visible = () => { if (document.visibilityState === 'visible') refresh(); };
    window.addEventListener(IDENTITY_CHANGED_EVENT, changed);
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    document.addEventListener('visibilitychange', visible);
    return () => {
      window.removeEventListener(IDENTITY_CHANGED_EVENT, changed);
      window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('online', refresh);
      document.removeEventListener('visibilitychange', visible);
      void client.cancelQueries();
      client.clear();
    };
  }, [cache, client, router]);

  return (
    <QueryClientProvider client={client}>
      <SessionScopeContext.Provider value={scope}>
        <Fragment key={pathname === '/feedback' ? 'public-feedback' : scope.epoch}>{children}</Fragment>
      </SessionScopeContext.Provider>
    </QueryClientProvider>
  );
};
