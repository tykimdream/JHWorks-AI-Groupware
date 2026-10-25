import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const configuration = { enabled: true, durationMinutes: 15, writeLimit: 20, requestLimit: 100 };

test('public demo entry hides shared password accounts', async ({ page }, testInfo) => {
  await page.route('**/api/v1/demo/configuration', (route) => route.fulfill({ json: configuration }));
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: '경비 정산, 작성부터 승인까지' })).toBeVisible();
  await expect(page.getByLabel('비밀번호')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '체험 시작하기' })).toBeEnabled();
  await mkdir('artifacts/feedback', { recursive: true });
  await page.screenshot({ path: `artifacts/feedback/entry-${testInfo.project.name}.png`, fullPage: true });
});

test('feedback preserves input across expired-session recovery and reports receipt', async ({ page }, testInfo) => {
  await page.route('**/api/v1/demo/configuration', (route) => route.fulfill({ json: configuration }));
  let posts = 0;
  await page.route('**/api/v1/demo/feedback', async (route) => {
    posts += 1;
    const body = route.request().postDataJSON();
    expect(body.consent).toBe(true);
    expect(body.message).toContain('승인 버튼');
    if (posts === 1) await route.fulfill({ status: 401, json: { error: { code: 'AUTHENTICATION_REQUIRED' } } });
    else await route.fulfill({ json: { id: 'feedback_synthetic_receipt', status: 'received' } });
  });
  await page.route('**/api/v1/demo/start', (route) => route.fulfill({ json: {} }));
  await page.goto('/feedback');
  const message = page.getByLabel('의견', { exact: true });
  await message.fill('승인 버튼을 찾기 어려웠습니다. 문서 옆에도 표시되면 좋겠습니다.');
  await message.focus();
  await page.keyboard.press('Tab');
  const consent = page.getByRole('checkbox');
  await expect(consent).toBeFocused();
  await page.keyboard.press('Space');
  await expect(consent).toBeChecked();
  await page.getByRole('button', { name: '의견 보내기' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '입력한 의견은 유지' })).toBeVisible();
  await expect(page).toHaveURL(/\/feedback$/);
  await expect(message).toHaveValue(/승인 버튼/);
  await page.getByRole('button', { name: '체험 연결하기' }).click();
  await expect(page.getByRole('status')).toContainText('체험이 연결됐습니다');
  await expect(page).toHaveURL(/\/feedback$/);
  await expect(message).toHaveValue(/승인 버튼/);
  await expect(consent).toBeChecked();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await mkdir('artifacts/feedback', { recursive: true });
  await page.screenshot({ path: `artifacts/feedback/form-${testInfo.project.name}.png`, fullPage: true });
  await page.getByRole('button', { name: '의견 보내기' }).click();
  await expect(page.getByRole('heading', { name: '의견을 접수했습니다' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('feedback_synthetic_receipt');
  expect(posts).toBe(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('feedback does not accept submissions while public demo is disabled', async ({ page }) => {
  await page.goto('/feedback');
  await expect(page.getByRole('status')).toContainText('피드백 접수를 준비 중');
  await expect(page.getByRole('button', { name: '의견 보내기' })).toHaveCount(0);
});
