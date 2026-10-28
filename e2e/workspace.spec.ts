import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await expect(page.getByRole('heading', { name: '어떤 업무를 도와드릴까요?' })).toBeVisible();
});

test('home → request → missing information → policy preview → explicit save → real home data', async ({
  page,
}, testInfo) => {
  const request = page.getByRole('textbox', { name: 'AI 업무 요청' });
  await expect(page.getByRole('button', { name: '출장 결재 준비', exact: true })).toBeEnabled();
  if (testInfo.project.name === 'desktop') {
    await page.keyboard.press('Control+j');
    await expect(request).toBeFocused();
  }
  await page.getByRole('button', { name: '출장 결재 준비', exact: true }).click();
  await expect(request).toHaveValue(/협력사 미팅/);
  await request.press('Control+Enter');
  await expect(page).toHaveURL('http://localhost:3100/approvals/ai-draft');
  await expect(page.getByRole('textbox', { name: '업무 요청', exact: true })).toHaveValue(
    /협력사 미팅/,
  );
  let saves = 0;
  page.on('request', (sent) => {
    if (sent.url().endsWith('/approval-draft-assistant/confirm')) saves++;
  });
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByText('출장 종료일은 언제인가요?', { exact: true })).toBeVisible();
  await expect(page.getByText('시뮬레이션 응답', { exact: false })).toBeVisible();
  await page.getByRole('textbox', { name: '추가 정보', exact: true }).fill('당일 출장입니다.');
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'CES 협력사 미팅 출장 신청', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('관련 출장 규정을 찾았습니다.', { exact: true })).toBeVisible();
  await expect(page.locator('.draft-preview-card')).toContainText('170,000');
  expect(saves).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({
    path: `artifacts/workspace-preview/draft-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole('button', { name: '확인하고 초안으로 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/?]+\/edit$/);
  await expect(page.getByRole('heading', { name: '결재 문서 수정' })).toBeVisible();
  expect(saves).toBe(1);
  await page.getByRole('link', { name: '업무 홈', exact: true }).click();
  await expect(
    page.locator('.home-document').filter({ hasText: 'CES 협력사 미팅 출장 신청' }).first(),
  ).toBeVisible();
  await expect(page.locator('.next-action-panel')).toContainText('시작한 업무를 마무리해요');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({
    path: `artifacts/workspace-preview/home-${testInfo.project.name}.png`,
    fullPage: true,
  });
});

test('a late response from the previous approval scope never replaces the active tab', async ({
  page,
}) => {
  let release!: () => void;
  let started!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const mineStarted = new Promise<void>((resolve) => {
    started = resolve;
  });
  const item = (title: string) => ({
    id: title,
    type: 'GENERAL',
    title,
    updatedAt: '2026-10-23T10:00:00Z',
    status: 'DRAFT',
    details: { kind: 'GENERAL' },
    lines: [],
    author: { name: '합성 작성자' },
    amount: null,
    content: '테스트 문서',
  });
  await page.route('**/api/v1/approvals?scope=*', async (route) => {
    const mine = route.request().url().endsWith('scope=mine');
    if (mine) {
      started();
      await held;
    }
    await route.fulfill({
      json: { total: 1, items: [item(mine ? '이전 탭의 늦은 응답' : '현재 결재할 문서')] },
    });
  });
  await page.goto('/approvals?scope=assigned');
  await expect(page.getByRole('heading', { name: '현재 결재할 문서', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '내가 결재할 문서', exact: true }).click();
  await expect(page.getByRole('heading', { name: '현재 결재할 문서', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '내가 작성한 문서', exact: true }).click();
  await mineStarted;
  await page.getByRole('tab', { name: '내가 결재할 문서', exact: true }).click();
  await expect(page.getByRole('heading', { name: '현재 결재할 문서', exact: true })).toBeVisible();
  release();
  await expect(page.getByRole('heading', { name: '이전 탭의 늦은 응답', exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByRole('tab', { name: '내가 결재할 문서', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
});

test('home request failures expose retry and recover using real data', async ({ page }) => {
  let fail = true;
  await page.route('**/api/v1/approvals?scope=mine', (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { error: { code: 'UNAVAILABLE', message: '현황 연결 실패' } },
        })
      : route.continue(),
  );
  await page.reload();
  await expect(page.getByRole('alert').filter({ hasText: '현황 연결 실패' })).toBeVisible();
  await expect(page.locator('.home-stat').first()).toContainText('—');
  fail = false;
  await page.getByRole('button', { name: '다시 불러오기', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '현황 연결 실패' })).toHaveCount(0);
  await expect(page.locator('.home-stat').first()).toContainText('0');
});

test('AI failure retains the request and offers a usable manual form', async ({ page }) => {
  await page.getByRole('button', { name: '출장 결재 준비', exact: true }).click();
  await page.getByRole('button', { name: 'AI 초안 작성으로 이동', exact: true }).click();
  await page.route('**/approval-draft-assistant/prepare', (route) =>
    route.fulfill({ status: 503, json: { error: { code: 'AI_DRAFT_UNAVAILABLE' } } }),
  );
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: 'AI 초안을 준비하지 못했습니다.' }),
  ).toBeVisible();
  await expect(page.getByRole('textbox', { name: '업무 요청', exact: true })).toHaveValue(
    /협력사 미팅/,
  );
  await page.getByRole('button', { name: '직접 작성으로 계속 →', exact: true }).click();
  await expect(page.getByRole('heading', { name: '결재 문서 작성', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toHaveValue(/협력사 미팅/);
});
