import type { ReactNode } from 'react';
import { publicMetadata, siteDescription } from '@/lib/site-metadata';

export const metadata = publicMetadata('체험 시작 — 경비 작성부터 승인까지', siteDescription, '/login');
export default function LoginLayout({ children }: { children: ReactNode }) { return children; }
