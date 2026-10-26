import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const login = async (page: Page) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인' }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await page.getByRole('link', { name: '근태·휴가' }).click();
  await expect(page.getByRole('heading', { name: '자연어로 휴가 상담' })).toBeVisible();
};

// Only the LLM and embedding adapters are fake. HTTP, auth, availability,
// preview signatures, persistence and the approval detail screen are real.
test('request → select → inspect → explicitly save one DRAFT', async ({ page }, testInfo) => {
  await login(page);
  await page.getByRole('textbox', { name: '휴가 질문' }).fill(
    '다음 주에 이틀 휴가를 가고 싶은데 우리 팀 일정과 겹치지 않는 날짜를 찾고 결재 초안도 만들어 줘',
  );
  await page.getByRole('button', { name: '휴가 상담 시작' }).click();
  const select = page.getByRole('button', { name: '이 날짜 선택하고 초안 확인' }).first();
  await expect(select).toBeVisible();
  await expect(page.getByRole('textbox', { name: '휴가 질문' })).toBeDisabled();
  await mkdir('docs/portfolio/screenshots', { recursive: true });
  await page.locator('.candidate-grid').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `docs/portfolio/screenshots/leave-candidates-${testInfo.project.name}.png` });
  await select.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: '저장 전 최종 확인' })).toBeVisible();
  await expect(select).toBeDisabled();
  await expect(page.getByText('아직 저장되지 않음')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await mkdir('docs/portfolio/screenshots', { recursive: true });
  await page.locator('.leave-draft-preview').screenshot({ path: `docs/portfolio/screenshots/leave-preview-${testInfo.project.name}.png` });
  let saves = 0;
  page.on('request', (request) => { if (request.url().endsWith('/draft/confirm')) saves++; });
  await page.getByRole('button', { name: '내용을 확인했고 초안으로 저장' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/approvals\/.+\?leaveRunId=/);
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('초안');
  expect(saves).toBe(1);
  await page.locator('.detail-title-row').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `docs/portfolio/screenshots/leave-draft-${testInfo.project.name}.png` });
});

test('provider failure offers the working manual path', async ({ page }) => {
  await login(page);
  await page.route('**/leave-agent/runs', (route) => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'LEAVE_ASSISTANT_UNAVAILABLE' } }),
  }));
  await page.getByRole('textbox', { name: '휴가 질문' }).fill('다음 주 이틀 휴가');
  await page.getByRole('button', { name: '휴가 상담 시작' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'AI 휴가 상담' })).toBeVisible();
  await page.getByRole('link', { name: '수동 휴가 후보 탐색' }).click();
  await page.getByRole('button', { name: '가능한 날짜 찾기' }).click();
  const manual = page.getByRole('link', { name: '이 날짜로 휴가 결재 작성' }).first();
  await expect(manual).toBeVisible();
  await manual.click();
  await expect(page).toHaveURL(/\/approvals\/new\?type=LEAVE/);
  await expect(page.getByRole('heading', { name: '결재 문서 작성' })).toBeVisible();
});

test('changed search removes old results and prevents overlapping requests', async ({ page }) => {
  await login(page);
  const seoulToday = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
  await expect(page.getByLabel('탐색 시작일')).toHaveValue(seoulToday);
  const search = page.getByRole('button', { name: '가능한 날짜 찾기' });
  await search.click();
  await expect(page.getByRole('link', { name: '이 날짜로 휴가 결재 작성' }).first()).toBeVisible();
  await page.getByLabel('사용할 연차').selectOption('1.0');
  await expect(page.getByRole('link', { name: '이 날짜로 휴가 결재 작성' })).toHaveCount(0);
  let release!: () => void;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/attendance/leave-availability?**', async (route) => {
    await hold;
    await route.continue();
  });
  await search.click();
  await expect(page.getByRole('button', { name: '계산 중…' })).toBeDisabled();
  await expect(page.getByLabel('사용할 연차')).toBeDisabled();
  release();
  await expect(search).toBeEnabled();
});


test('an account change clears the previous employee consultation', async ({ page, context }) => {
  await login(page);
  await page.getByRole('textbox', { name: '휴가 질문' }).fill('다음 주 이틀 휴가');
  await page.getByRole('button', { name: '휴가 상담 시작' }).click();
  await expect(page.getByRole('button', { name: '이 날짜 선택하고 초안 확인' }).first()).toBeVisible();
  const switched = await context.request.post('http://localhost:8100/api/v1/auth/login', {
    data: { email: 'doyun.choi@jhworks.test', password: 'demo1234' },
  });
  expect(switched.ok()).toBe(true);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.locator('.profile-card')).toContainText('최도윤');
  await expect(page.getByRole('button', { name: '이 날짜 선택하고 초안 확인' })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: '휴가 질문' })).toBeEmpty();
});
