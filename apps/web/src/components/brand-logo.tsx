'use client';

import { GuardedLink as Link } from '@/components/navigation-guard';

import { BrandMark, BrandWordmark } from '@/components/brand-mark';

export function BrandLogo({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <Link
      href="/"
      aria-label="JHWorks 홈으로"
      className={`tw:inline-flex tw:shrink-0 tw:min-h-11 tw:items-center tw:gap-2.5 tw:rounded tw:max-[480px]:gap-2 tw:no-underline tw:focus-visible:outline-2 tw:focus-visible:outline-offset-4 ${inverse ? 'tw:text-white tw:focus-visible:outline-white!' : 'tw:text-jhw-text tw:focus-visible:outline-jhw-primary'}`}
    >
      {compact ? <BrandMark color="currentColor" /> : (
        <BrandWordmark className="tw:block tw:h-6 tw:w-auto tw:max-[480px]:h-5" />
      )}
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
