'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createContext, useContext, useRef, type ComponentProps, type ReactNode } from 'react';

type Navigation = () => void;
type Guard = (navigate: Navigation) => void;
const NavigationContext = createContext<{ current: Guard | null } | null>(null);

export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const guard = useRef<Guard | null>(null);
  return <NavigationContext.Provider value={guard}>{children}</NavigationContext.Provider>;
}

export function useNavigationGuard() {
  const guard = useContext(NavigationContext);
  if (!guard) throw new Error('NavigationGuardProvider is required');
  return guard;
}

// Next handles new tabs, downloads and external links before onNavigate.
export function GuardedLink({ href, onNavigate, scroll, replace, ...props }: Omit<ComponentProps<typeof Link>, 'href'> & { href: string }) {
  const guard = useNavigationGuard();
  const router = useRouter();
  return <Link {...props} href={href} scroll={scroll} replace={replace} onNavigate={(event) => {
    onNavigate?.(event);
    if (!guard.current) return;
    event.preventDefault();
    guard.current(() => (replace ? router.replace : router.push)(href, { scroll }));
  }} />;
}
