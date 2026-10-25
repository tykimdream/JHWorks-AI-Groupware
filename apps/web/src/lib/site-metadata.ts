import type { Metadata } from 'next';

export const siteOrigin = 'https://groupware.pikan.dev';
export const siteTitle = 'JHWorks — 경비 작성부터 승인까지';
export const siteDescription = '가상 기업의 경비 작성·보완·결재·승인을 직접 체험하는 AI 그룹웨어 포트폴리오입니다. 업무 흐름과 JHW Pattern 디자인 시스템을 살펴보세요.';
const image = { url: '/opengraph-image', width: 1200, height: 630, alt: 'JHWorks — AI workspace. From request to approval.' };

export function publicMetadata(title: string, description: string, path: string): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: { index: true, follow: true },
    openGraph: { title, description, url: path, siteName: 'JHWorks', locale: 'ko_KR', type: 'website', images: [image] },
    twitter: { card: 'summary_large_image', title, description, images: ['/opengraph-image'] },
  };
}

export const sharedMetadata: Metadata = {
  metadataBase: new URL(siteOrigin),
  applicationName: 'JHWorks',
  title: { default: siteTitle, template: '%s | JHWorks' },
  description: siteDescription,
  // Authenticated workspace URLs must never publish document or employee data in snippets.
  robots: { index: false, follow: true },
  openGraph: { title: siteTitle, description: siteDescription, url: '/', siteName: 'JHWorks', locale: 'ko_KR', type: 'website', images: [image] },
  twitter: { card: 'summary_large_image', title: siteTitle, description: siteDescription, images: ['/opengraph-image'] },
};
