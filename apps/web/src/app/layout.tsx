import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { connection } from 'next/server';

import '@jhworks/pattern/tokens.css';
import '@jhworks/pattern/legacy.css';
import './tailwind.css';
import './globals.css';
import './workspace.css';
import '@jhworks/pattern/components.css';

export const metadata: Metadata = {
  title: 'JHWorks AI Groupware',
  description: 'A synthetic enterprise workflow and approval platform',
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // Every HTML response must render with its own CSP nonce.
  await connection();
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
