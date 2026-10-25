import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: '의견 남기기',
  description: 'JHWorks 체험 중 불편한 점과 개선 아이디어를 비공개로 남겨주세요.',
  robots: { index: false, follow: true },
};
export default function FeedbackLayout({ children }: { children: ReactNode }) { return children; }
