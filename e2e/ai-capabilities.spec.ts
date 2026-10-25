import { expect, test } from '@playwright/test';

const unavailable = {
  enabled: false,
  durationMinutes: 15,
  writeLimit: 20,
  requestLimit: 100,
  aiCapabilities: {
    approvalDraft: false,
    approvalReview: false,
    leaveAssistant: false,
    workAssistant: false,
    policyEmbedding: false,
  },
};

for (const legacy of [false, true]) {
  test(`private AI unavailable preserves manual workflow (legacy configuration=${legacy})`, async ({ page }) => {
    const configuration = legacy
      ? { enabled: false, durationMinutes: 15, writeLimit: 20, requestLimit: 100 }
      : unavailable;
    await page.route('**/api/v1/demo/configuration', (route) => route.fulfill({ json: configuration }));
    let paidRequests = 0;
    page.on('request', (request) => {
      if (request.method() === 'POST' && /assistant|ai-review/.test(request.url())) paidRequests++;
    });
    await page.goto('/login');
    await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
    await expect(page.getByRole('heading', { name: '경비 정산부터 시작해 보세요' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'AI 초안 작성', exact: true })).toHaveCount(0);
    await page.goto('/approvals/ai-draft');
    await expect(page.getByText('현재 이 AI 기능을 사용할 수 없습니다.', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'AI로 초안 준비', exact: true })).toHaveCount(0);
    await page.getByRole('link', { name: '직접 작성하기 →', exact: true }).click();
    await expect(page).toHaveURL(/\/approvals\/new$/);
    await expect(page.getByRole('textbox', { name: '제목', exact: true })).toBeVisible();
    expect(paidRequests).toBe(0);
  });
}

test('each AI page uses its own server capability', async ({ page }) => {
  await page.route('**/api/v1/demo/configuration', (route) => route.fulfill({
    json: { ...unavailable, aiCapabilities: { ...unavailable.aiCapabilities, approvalDraft: true } },
  }));
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toBeVisible();
  await page.goto('/assistant');
  await expect(page.getByText('현재 이 AI 기능을 사용할 수 없습니다.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: /조회하기/ })).toHaveCount(0);
  await page.goto('/attendance');
  await expect(page.getByText('현재 이 AI 기능을 사용할 수 없습니다.', { exact: false })).toBeVisible();
  await expect(page.getByRole('heading', { name: '자연어로 휴가 상담' })).toHaveCount(0);
});

test('configuration failure offers manual entry without enabling AI', async ({ page }) => {
  await page.route('**/api/v1/demo/configuration', (route) => route.fulfill({
    status: 503, json: { error: { code: 'UNAVAILABLE', message: 'synthetic failure' } },
  }));
  // Enter through the isolated fixture's password endpoint; /login deliberately waits for configuration.
  const response = await page.request.post('/api/v1/auth/login', {
    data: { email: 'seojin.yoon@jhworks.test', password: 'demo1234' },
    headers: { Origin: 'http://localhost:3100' },
  });
  expect(response.ok()).toBeTruthy();
  await page.goto('/approvals/ai-draft');
  await expect(page.getByRole('alert').filter({ hasText: 'AI 사용 설정을 불러오지 못했습니다.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI로 초안 준비', exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: '직접 작성하기 →', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '제목', exact: true })).toBeVisible();
});
