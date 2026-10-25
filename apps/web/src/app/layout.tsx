import type { ReactNode } from 'react';
import { connection } from 'next/server';
import { sharedMetadata } from '@/lib/site-metadata';
import { SessionDataProvider } from '@/components/session-data-provider';

import '@jhworks/pattern/tokens.css';
import '@jhworks/pattern/legacy.css';
import './tailwind.css';
import './globals.css';
import './workspace.css';
import '@jhworks/pattern/components.css';

export const metadata = sharedMetadata;

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // Every HTML response must render with its own CSP nonce.
  await connection();
  return (
    <html lang="ko">
      <body><SessionDataProvider>{children}</SessionDataProvider></body>
    </html>
  );
}
