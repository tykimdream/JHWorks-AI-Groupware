import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';

test('public pages have accessible home logos and fit desktop and mobile', async ({ page }, testInfo) => {
  await mkdir('artifacts/brand', { recursive: true });
  for (const path of ['/pattern', '/feedback', '/login']) {
    await page.goto(path);
    const logo = page.getByRole('link', { name: 'JHWorks 홈으로', exact: true });
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute('href', '/');
    await logo.focus();
    await expect(logo).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `artifacts/brand/${path.slice(1)}-${testInfo.project.name}.png`, fullPage: false });
  }
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
  await page.goto('/pattern');
  await page.getByRole('link', { name: 'JHWorks 홈으로', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
});

test('share crawlers get absolute metadata, a real PNG, canonical public pages and safe indexing', async ({ request }) => {
  const response = await request.get('/login', { headers: { 'User-Agent': 'Twitterbot/1.0' } });
  const html = await response.text();
  expect(html).toContain('property="og:title"');
  expect(html).toContain('property="og:description"');
  expect(html).toContain('name="twitter:card" content="summary_large_image"');
  expect(html).toContain('rel="canonical" href="https://groupware.pikan.dev/login"');
  expect(html).toContain('name="robots" content="index, follow"');
  const imageUrl = html.match(/property="og:image" content="([^"]+)"/)?.[1];
  expect(imageUrl).toMatch(/^https:\/\/groupware\.pikan\.dev\/opengraph-image/);
  const imagePath = new URL(imageUrl!).pathname;
  const image = await request.get(imagePath);
  expect(image.ok()).toBe(true);
  expect(image.headers()['content-type']).toContain('image/png');
  const bytes = await image.body();
  expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  expect(bytes.readUInt32BE(16)).toBe(1200);
  expect(bytes.readUInt32BE(20)).toBe(630);
  await mkdir('artifacts/brand', { recursive: true });
  await writeFile('artifacts/brand/opengraph.png', bytes);
  const pattern = await (await request.get('/pattern')).text();
  expect(pattern).toContain('rel="canonical" href="https://groupware.pikan.dev/pattern"');
  expect(pattern).toContain('JHW Pattern — 토큰과 컴포넌트 사용 가이드');
  for (const path of ['/', '/approvals', '/approvals/synthetic-document', '/feedback']) {
    const page = await (await request.get(path)).text();
    expect(page).toContain('name="robots" content="noindex, follow"');
    expect(page).not.toContain('rel="canonical"');
  }
  const sitemap = await (await request.get('/sitemap.xml')).text();
  expect(sitemap).toContain('<loc>https://groupware.pikan.dev/login</loc>');
  expect(sitemap).toContain('<loc>https://groupware.pikan.dev/pattern</loc>');
  expect(sitemap).not.toContain('/approvals');
  expect(sitemap).not.toContain('/feedback');
  const robots = await (await request.get('/robots.txt')).text();
  expect(robots).toContain('Sitemap: https://groupware.pikan.dev/sitemap.xml');
  expect(robots).not.toContain('Disallow: /approvals');
});
