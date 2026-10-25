import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';

test('common session queries are shared across home, studio and manual form', async ({ page }, testInfo) => {
  const counts = { configuration: 0, identity: 0 };
  page.on('response', (response) => {
    if (response.request().method() !== 'GET' || response.status() !== 200) return;
    if (response.url().endsWith('/api/v1/demo/configuration')) counts.configuration++;
    if (response.url().endsWith('/api/v1/employees/me')) counts.identity++;
  });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const home = { ...counts };
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  await expect(page.getByRole('button', { name: 'AI로 초안 준비', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const studio = { ...counts };
  await page.getByRole('link', { name: '새 결재 작성', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '제목', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const manual = { ...counts };
  expect(home).toEqual({ configuration: 2, identity: 1 });
  expect(studio).toEqual(home);
  expect(manual).toEqual(home);
  await mkdir('artifacts/session-data', { recursive: true });
  await writeFile(`artifacts/session-data/after-${testInfo.project.name}.json`, JSON.stringify({ home, studio, manual }, null, 2));
});

const login = async (page: import('@playwright/test').Page) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeVisible();
  await page.waitForLoadState('networkidle');
};

const changeAccount = async (page: import('@playwright/test').Page) => {
  const response = await page.request.post('/api/v1/auth/login', {
    data: { email: 'doyun.choi@jhworks.test', password: 'demo1234' },
    headers: { Origin: 'http://localhost:3100' },
  });
  expect(response.ok()).toBe(true);
};

const focus = (page: import('@playwright/test').Page) =>
  page.evaluate(() => window.dispatchEvent(new Event('focus')));

// A healthy refresh hides the content while verifying identity, without remounting its input.
test('focus and visibility share an in-flight identity check and retain a healthy draft', async ({ page }) => {
  await login(page);
  await page.getByRole('textbox', { name: 'AI 업무 요청' }).fill('입력 보존 확인');
  let release!: () => void;
  let started!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const ready = new Promise<void>((resolve) => { started = resolve; });
  let requests = 0;
  await page.route('**/api/v1/employees/me', async (route) => {
    requests++;
    const response = await route.fetch();
    started();
    await held;
    await route.fulfill({ response });
  });
  await focus(page);
  await ready;
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeHidden();
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  release();
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toHaveValue('입력 보존 확인');
  expect(requests).toBe(1);
});

for (const status of [200, 401]) {
  test(`a delayed previous identity ${status} cannot replace or expire the new session`, async ({ page }) => {
    await login(page);
    await page.getByRole('textbox', { name: 'AI 업무 요청' }).fill('이전 계정 입력');
    let release!: () => void;
    let started!: () => void;
    let finished!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    const ready = new Promise<void>((resolve) => { started = resolve; });
    const done = new Promise<void>((resolve) => { finished = resolve; });
    let first = true;
    await page.route('**/api/v1/employees/me', async (route) => {
      if (!first) return route.continue();
      first = false;
      const response = await route.fetch();
      started();
      await held;
      try {
        if (status === 200) await route.fulfill({ response });
        else await route.fulfill({ status, json: { error: { code: 'AUTHENTICATION_REQUIRED' } } });
      } finally { finished(); }
    });
    await focus(page);
    await ready;
    await changeAccount(page);
    await page.evaluate(() => window.dispatchEvent(new Event('jhworks:identity-changed')));
    await expect(page.locator('.profile-card')).toContainText('최도윤');
    release();
    await done;
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.profile-card')).toContainText('최도윤');
    await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeEmpty();
    await expect(page).toHaveURL('http://localhost:3100/');
  });
}

test('a cookie change outside the app clears parent page input on focus', async ({ page }) => {
  await login(page);
  await page.getByRole('textbox', { name: 'AI 업무 요청' }).fill('이전 계정 입력');
  await changeAccount(page);
  await focus(page);
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeEmpty();
});

test('current identity expiry goes to login and the next account starts fresh', async ({ page }) => {
  await login(page);
  await page.route('**/api/v1/employees/me', (route) => route.fulfill({
    status: 401, json: { error: { code: 'AUTHENTICATION_REQUIRED' } },
  }));
  await focus(page);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator('.profile-card')).toHaveCount(0);
  await page.unroute('**/api/v1/employees/me');
  await page.getByRole('button', { name: /결재자 · 최도윤/ }).click();
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('최도윤');
});

test('failed password login retains input without an automatic retry', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('비밀번호', { exact: true }).fill('incorrect-synthetic-password');
  let attempts = 0;
  page.on('request', (request) => { if (request.url().endsWith('/auth/login')) attempts++; });
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.error-banner')).toBeVisible();
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveValue('incorrect-synthetic-password');
  await expect(page.getByRole('button', { name: 'Demo 로그인', exact: true })).toBeEnabled();
  expect(attempts).toBe(1);
});

// Mutations do not take the query AbortSignal. This exercises the generation guard itself.
test('a late unabortable AI request 401 cannot log out a newly authenticated account', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill('CES 경비 17만원 정산');
  let release!: () => void;
  let started!: () => void;
  let finished!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const ready = new Promise<void>((resolve) => { started = resolve; });
  const done = new Promise<void>((resolve) => { finished = resolve; });
  await page.route('**/approval-draft-assistant/prepare', async (route) => {
    started();
    await held;
    try {
      await route.fulfill({ status: 401, json: { error: { code: 'AUTHENTICATION_REQUIRED' } } });
    } finally { finished(); }
  });
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await ready;
  await changeAccount(page);
  await page.evaluate(() => window.dispatchEvent(new Event('jhworks:identity-changed')));
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  release();
  await done;
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(/\/approvals\/ai-draft$/);
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  await expect(page.getByRole('textbox', { name: '업무 요청', exact: true })).toBeEmpty();
});
