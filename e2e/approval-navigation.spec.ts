import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
  const document = (id: string, scope: string) => ({
    id, type: 'GENERAL', title: `${scope} 문서 ${id}`, content: '합성 탐색 검증',
    status: 'DRAFT', version: 1, amount: null, details: { kind: 'GENERAL' }, lines: [],
    author: { id: 'synthetic-author', name: '합성 작성자', position: '사원' },
    createdAt: '2026-10-25T01:00:00Z', updatedAt: '2026-10-25T01:00:00Z',
    submittedAt: null, decidedAt: null,
  });
  await page.route('**/api/v1/approvals?scope=*', (route) => {
    const scope = new URL(route.request().url()).searchParams.get('scope')!;
    return route.fulfill({ json: {
      total: 40,
      items: Array.from({ length: 40 }, (_, index) => document(`nav-${index}`, scope)),
    } });
  });
  await page.route('**/api/v1/approvals/nav-*', (route) => {
    const id = new URL(route.request().url()).pathname.split('/').pop()!;
    return route.fulfill({ json: document(id, 'assigned') });
  });
});

test('list scope follows URL, reload and browser back/forward', async ({ page }) => {
  await page.goto('/approvals');
  await expect(page.getByRole('tab', { name: '내가 작성한 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: '내가 결재할 문서', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\?scope=assigned$/);
  await expect(page.getByRole('tab', { name: '내가 결재할 문서', exact: true })).toBeFocused();
  await page.reload();
  await expect(page.getByRole('tab', { name: '내가 결재할 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: '내가 작성한 문서', exact: true }).click();
  await expect(page).toHaveURL(/scope=mine$/);
  await page.goBack();
  await expect(page.getByRole('tab', { name: '내가 결재할 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'assigned 문서 nav-0', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('tab', { name: '내가 작성한 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'mine 문서 nav-0', exact: true })).toBeVisible();
});

test('detail returns to the selected scope and visible focused row after async loading', async ({ page }, testInfo) => {
  await page.goto('/approvals?scope=assigned');
  await page.locator('#approval-nav-30').click();
  await expect(page).toHaveURL(/\/approvals\/nav-30\?from=assigned$/);
  await page.reload(); // The return contract survives a detail reload without storage.
  const back = page.getByRole('link', { name: '← 목록으로', exact: true });
  await expect(back).toHaveAttribute('href', '/approvals?scope=assigned#approval-nav-30');
  await back.click();
  await expect(page.getByRole('tab', { name: '내가 결재할 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  const row = page.locator('#approval-nav-30');
  await expect(row).toBeFocused();
  await expect(row).toBeInViewport();
  await expect(page).toHaveURL(/scope=assigned#approval-nav-30$/);
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({ path: `artifacts/workspace-preview/list-return-${testInfo.project.name}.png` });
});

test('unknown scope, missing rows and untrusted return destinations fall back safely', async ({ page }) => {
  await page.goto('/approvals?scope=unknown#approval-deleted');
  await expect(page.getByRole('tab', { name: '내가 작성한 문서', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'mine 문서 nav-0', exact: true })).toBeVisible();
  await page.goto('/approvals/nav-1?from=https%3A%2F%2Fexample.com');
  const back = page.getByRole('link', { name: '← 목록으로', exact: true });
  await expect(back).toHaveAttribute('href', '/approvals');
  await back.click();
  await expect(page).toHaveURL('http://localhost:3100/approvals');
});
