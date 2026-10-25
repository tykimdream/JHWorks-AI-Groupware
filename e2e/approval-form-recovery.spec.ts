import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const title = (page: Page) => page.getByRole('textbox', { name: '제목', exact: true });
const key = 'jhworks:approval-form:emp_sales_001:new';
const dialog = (page: Page) => page.getByRole('dialog', { name: '저장하지 않고 이동할까요?' });
async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
  await page.goto('/approvals/new?type=EXPENSE');
}

test('unsaved link and cancel navigation require confirmation, Escape retains input and restores focus', async ({ page }, testInfo) => {
  await login(page);
  await title(page).fill('이동 전 합성 경비');
  const nav = page.getByRole('link', { name: '업무 홈', exact: true });
  await nav.click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page).getByRole('button', { name: '계속 작성' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog(page).getByRole('button', { name: '저장하지 않고 이동' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog(page)).not.toBeVisible();
  await expect(nav).toBeFocused();
  await expect(title(page)).toHaveValue('이동 전 합성 경비');
  await page.getByRole('button', { name: '취소', exact: true }).click();
  await expect(dialog(page)).toBeVisible();
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({ path: `artifacts/workspace-preview/unsaved-${testInfo.project.name}.png` });
  await dialog(page).getByRole('button', { name: '저장하지 않고 이동' }).click();
  await expect(page).toHaveURL(/\/approvals$/);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
});

test('reload offers explicit recovery of expense values without an API write', async ({ page }) => {
  await login(page);
  await title(page).fill('복원할 합성 경비');
  await page.getByLabel('사용처', { exact: true }).fill('합성 코레일');
  await page.getByLabel('실제 지출 금액 (원)').fill('170000');
  let writes = 0;
  page.on('request', (request) => { if (request.method() === 'POST' && request.url().endsWith('/approvals')) writes++; });
  page.once('dialog', (event) => event.accept());
  await page.reload();
  await expect(title(page)).toBeEmpty();
  await page.getByRole('button', { name: '이전 입력 이어쓰기' }).click();
  await expect(title(page)).toHaveValue('복원할 합성 경비');
  await expect(page.getByLabel('사용처', { exact: true })).toHaveValue('합성 코레일');
  await expect(page.getByLabel('실제 지출 금액 (원)')).toHaveValue('170000');
  expect(writes).toBe(0);
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/?]+$/);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
  expect(writes).toBe(1);
});

test('save failure keeps fields and storage failure warns without blocking server save', async ({ page }) => {
  await login(page);
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error('synthetic denied'); }; });
  await title(page).fill('실패 후 보존');
  await expect(page.getByRole('status').filter({ hasText: '임시 보관하지 못했습니다' })).toBeVisible();
  await page.route('**/api/v1/approvals', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({ status: 503, json: { error: { code: 'SYNTHETIC_FAILURE', message: '합성 저장 실패' } } });
  });
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(title(page)).toHaveValue('실패 후 보존');
  await page.unroute('**/api/v1/approvals');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/?]+$/);
});

test('logout clears temporary forms and invalid or expired storage is rejected', async ({ page }) => {
  await login(page);
  await title(page).fill('계정 변경 전 합성 입력');
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), key)).not.toBeNull();
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
  await login(page);
  await page.evaluate((key) => sessionStorage.setItem(key, JSON.stringify({ schema: 1, version: null, expiresAt: Date.now() - 1, values: {} })), key);
  await page.reload();
  await expect(title(page)).toBeVisible(); // A missing button also matches before hydration.
  await expect(page.getByRole('button', { name: '이전 입력 이어쓰기' })).toHaveCount(0);
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
  await page.evaluate((key) => sessionStorage.setItem(key, '{broken'), key);
  await page.reload();
  await expect(title(page)).toBeEmpty();
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
});

test('account change and a save-time session expiration clear old inputs', async ({ page }) => {
  await login(page);
  await title(page).fill('이전 계정 입력');
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), key)).not.toBeNull();
  const switched = await page.request.post('/api/v1/auth/login', {
    data: { email: 'doyun.choi@jhworks.test', password: 'demo1234' },
    headers: { Origin: 'http://localhost:3100' },
  });
  expect(switched.ok()).toBe(true);
  await page.evaluate(() => window.dispatchEvent(new Event('jhworks:identity-changed')));
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  await expect(title(page)).toBeEmpty();
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
  await title(page).fill('만료 시 지울 입력');
  await page.route('**/api/v1/approvals', (route) => route.fulfill({ status: 401, json: { error: { code: 'AUTHENTICATION_REQUIRED' } } }));
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter((key) => key.startsWith('jhworks:approval-form:')))).toEqual([]);
});

test('edit recovery requires the same base version and preserves list origin through save', async ({ page }) => {
  await login(page);
  await title(page).fill('버전과 복귀 검증');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/?]+$/);
  const id = new URL(page.url()).pathname.split('/').pop()!;
  await page.goto(`/approvals/${id}?from=mine`);
  await page.getByRole('link', { name: '수정', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/approvals/${id}/edit\\?from=mine$`));
  await title(page).fill('버전 불일치면 복원하지 않음');
  const editKey = key.replace(':new', `:${id}`);
  await expect.poll(() => page.evaluate((key) => sessionStorage.getItem(key), editKey)).not.toBeNull();
  await page.evaluate((key) => {
    const entry = JSON.parse(sessionStorage.getItem(key)!);
    entry.version += 100;
    sessionStorage.setItem(key, JSON.stringify(entry));
  }, editKey);
  page.once('dialog', (event) => event.accept());
  await page.reload();
  await expect(title(page)).toHaveValue('버전과 복귀 검증');
  await expect(page.getByRole('button', { name: '이전 입력 이어쓰기' })).toHaveCount(0);
  await title(page).fill('수정 후 목록으로');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/approvals/${id}\\?from=mine$`));
  await expect(page.getByRole('link', { name: '← 목록으로' })).toHaveAttribute('href', `/approvals?scope=mine#approval-${id}`);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), editKey)).toBeNull();
});
