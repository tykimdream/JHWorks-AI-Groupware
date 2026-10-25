import Link from 'next/link';

// A linked pair of strokes: one request moving through a shared workflow.
export function BrandLogo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" aria-label="JHWorks 홈으로" className="tw:inline-flex tw:shrink-0 tw:items-center tw:gap-2.5 tw:rounded-lg tw:text-jhw-text tw:no-underline tw:focus-visible:outline-2 tw:focus-visible:outline-offset-4 tw:focus-visible:outline-jhw-primary">
      <svg viewBox="0 0 40 40" width="36" height="36" fill="none" aria-hidden="true">
        <rect width="40" height="40" rx="12" fill="var(--jhw-color-primary)" />
        <path d="M14 12v13a5 5 0 0 1-5 5M22 12v16m0-8a6 6 0 0 1 6-6v14" stroke="white" strokeWidth="3.5" strokeLinecap="round" />
        <circle cx="14" cy="7" r="1.8" fill="white" />
      </svg>
      {!compact && <span className="tw:text-xl tw:font-bold tw:tracking-tight">JHWorks</span>}
    </Link>
  );
}

export function PublicPageHeader() {
  return (
    <header className="tw:mb-8 tw:flex tw:w-full tw:items-center tw:justify-between tw:gap-4 tw:border-0 tw:border-b tw:border-solid tw:border-jhw-border tw:pb-5">
      <BrandLogo />
      <span className="tw:text-xs tw:font-medium tw:tracking-wide tw:text-jhw-muted">AI WORKSPACE</span>
    </header>
  );
}
