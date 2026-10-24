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
