import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
});

test('home proactively offers missing facts and duplicate evidence that opens an authorized document', async ({
  page,
}, testInfo) => {
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
  const payload = {
    type: 'EXPENSE',
    title: 'CES 교통비 · 기존 정산',
    content: '합성 경비 중복 점검 시나리오',
    amount: 170000,
    details: {
      kind: 'EXPENSE',
      expenseDate: date,
      merchant: `점검용 코레일 ${testInfo.project.name}`,
      category: 'TRANSPORTATION',
      purpose: 'CES 출장 교통비',
    },
  };
  const old = await page.request.post('/api/v1/approvals', { data: payload });
  expect(old.status()).toBe(201);
  const oldId = (await old.json()).id;
  const current = await page.request.post('/api/v1/approvals', {
    data: {
      ...payload,
      title: 'CES 교통비 · 제출 전 확인',
      details: { ...payload.details, purpose: '' },
    },
  });
  expect(current.status()).toBe(201);
  const currentId = (await current.json()).id;
  await page.reload();
  const insight = page
    .getByRole('region', { name: '미리 확인할 경비' })
    .locator('article')
    .filter({ has: page.locator(`.expense-insight-title[href="/approvals/${currentId}"]`) });
  await expect(insight).toContainText('업무 목적');
  await expect(insight).toContainText('같은 지출이 이미 등록됐을 수 있어요');
  await page.evaluate(() => window.scrollTo(0, 0));
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({
    path: `artifacts/workspace-preview/insights-home-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await insight.locator('.expense-insight-title').click();
  await expect(page).toHaveURL(new RegExp(`/approvals/${currentId}$`));
  const checks = page.getByRole('region', { name: '경비 사전 확인' });
  await expect(checks).toContainText('업무 목적');
  await expect(
    checks.getByRole('link', { name: 'CES 교통비 · 기존 정산', exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `artifacts/workspace-preview/insights-detail-${testInfo.project.name}.png`,
    fullPage: true,
  });
  let patches = 0;
  page.on('request', (request) => { if (request.method() === 'PATCH' && request.url().endsWith(`/approvals/${currentId}`)) patches++; });
  await checks.getByRole('link', { name: '업무 목적 보완하기 →', exact: true }).click();
  const purpose = page.getByRole('textbox', { name: '업무상 지출 목적', exact: true });
  await expect(purpose).toBeFocused();
  await expect(purpose).toBeInViewport();
  await expect(purpose).toBeEmpty();
  await page.screenshot({ path: `artifacts/workspace-preview/insights-repair-${testInfo.project.name}.png` });
  expect(patches).toBe(0);
  await purpose.fill('CES 출장 이동');
  expect(patches).toBe(0);
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/approvals/${currentId}\\?from=mine$`));
  await expect(checks).not.toContainText('업무 목적 보완하기');
  expect(patches).toBe(1);
  await checks.getByRole('link', { name: 'CES 교통비 · 기존 정산', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/approvals/${oldId}$`));
  await expect(
    page.getByRole('heading', { name: 'CES 교통비 · 기존 정산', exact: true }),
  ).toBeVisible();
});

test('failed expense insight checks never claim that there are no issues and can be retried', async ({
  page,
}) => {
  let fail = true;
  await page.route('**/api/v1/approvals/expense-insights', (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { error: { code: 'UNAVAILABLE', message: '경비 점검 연결 실패' } },
        })
      : route.continue(),
  );
  await page.reload();
  const insights = page.getByRole('region', { name: '미리 확인할 경비' });
  await expect(insights.getByRole('alert')).toContainText('경비 점검 연결 실패');
  await expect(insights).not.toContainText('찾지 못했습니다');
  fail = false;
  await insights.getByRole('button', { name: '다시 확인', exact: true }).click();
  await expect(insights.getByRole('alert')).toHaveCount(0);
  await expect(insights).toContainText('제안만으로 문서를 변경하거나 제출하지 않습니다.');
});

test('approver sees read-only checks and rejection comments remain visible during revision', async ({ page }, testInfo) => {
  const headers = { Origin: 'http://localhost:3100' };
  const created = await page.request.post('/api/v1/approvals', { headers, data: {
    type: 'EXPENSE', title: '반려 보완 흐름', content: '합성 검증', amount: 170000,
    details: { kind: 'EXPENSE', expenseDate: '2026-01-08', merchant: '합성 코레일', category: 'TRANSPORTATION', purpose: 'CES 출장' },
  } });
  expect(created.ok()).toBe(true);
  const draft = await created.json();
  const submitted = await page.request.post(`/api/v1/approvals/${draft.id}/submit`, { headers, data: { version: draft.version } });
  expect(submitted.ok()).toBe(true);
  const pending = await submitted.json();
  const manager = await page.request.post('/api/v1/auth/login', { headers, data: { email: 'doyun.choi@jhworks.test', password: 'demo1234' } });
  expect(manager.ok()).toBe(true);
  await page.goto(`/approvals/${draft.id}?from=assigned`);
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  await expect(page.getByRole('region', { name: '경비 사전 확인' })).toBeVisible();
  await expect(page.getByRole('link', { name: /보완하기/ })).toHaveCount(0);
  const note = '이동 구간과 증빙 참조를 보완해주세요.\n원본은 별도로 확인합니다.';
  const rejected = await page.request.post(`/api/v1/approvals/${draft.id}/reject`, { headers, data: { version: pending.version, comment: note } });
  expect(rejected.ok()).toBe(true);
  const author = await page.request.post('/api/v1/auth/login', { headers, data: { email: 'seojin.yoon@jhworks.test', password: 'demo1234' } });
  expect(author.ok()).toBe(true);
  await page.goto(`/approvals/${draft.id}?from=mine`);
  await expect(page.getByRole('region', { name: '최근 반려 의견' })).toContainText(note);
  await page.getByRole('button', { name: '다시 수정하기', exact: true }).click();
  await page.getByRole('dialog', { name: '재작성 확인' }).getByRole('button', { name: '확인하고 재작성' }).click();
  await page.getByRole('link', { name: '수정', exact: true }).click();
  await expect(page.getByRole('region', { name: '최근 반려 의견' })).toContainText(note);
  await expect(page.getByRole('textbox', { name: '업무상 지출 목적', exact: true })).toHaveValue('CES 출장');
  // Context is read-only: the rejection comment is never copied into business fields.
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toHaveValue('합성 검증');
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({ path: `artifacts/workspace-preview/rejection-edit-${testInfo.project.name}.png` });
});
