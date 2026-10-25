import { expect, test, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
}
async function failDraft(page: Page) {
  await page.route('**/approval-draft-assistant/prepare', (route) => route.fulfill({
    status: 503, json: { error: { code: 'AI_DRAFT_UNAVAILABLE' } },
  }));
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByRole('button', { name: '직접 작성으로 계속 →' })).toBeVisible();
}

test('failed AI transfers literal input to an unsaved form and consumes it once', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  const original = '이번 CES 경비는 17만원입니다. <script>synthetic</script>';
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill(original);
  await failDraft(page);
  let writes = 0;
  page.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/approvals')) writes++; });
  await page.getByRole('button', { name: '직접 작성으로 계속 →' }).click();
  await expect(page).toHaveURL(/\/approvals\/new\?handoff=manual$/);
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toHaveValue(original);
  await expect(page.getByRole('textbox', { name: '제목', exact: true })).toBeEmpty();
  await expect(page.getByRole('status')).toContainText('아직 저장되지 않았습니다');
  expect(writes).toBe(0);
  expect(page.url()).not.toContain('17');
  await page.reload();
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toBeEmpty();
  await expect(page.getByRole('status')).toContainText('이어받을 입력이 없거나');
});

test('storage failure retains AI input and does not navigate', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill('보존할 합성 요청');
  await failDraft(page);
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error('synthetic storage denied'); }; });
  await page.getByRole('button', { name: '직접 작성으로 계속 →' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '입력을 옮기지 못했습니다' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '업무 요청', exact: true })).toHaveValue('보존할 합성 요청');
  await expect(page).toHaveURL(/\/approvals\/ai-draft$/);
});

test('expired, other-account and implicit handoffs are not restored', async ({ page }) => {
  await login(page);
  await page.evaluate(() => {
    sessionStorage.setItem('jhworks:manual-draft:emp_sales_001', JSON.stringify({ content: '만료된 합성 요청', expiresAt: Date.now() - 1 }));
    sessionStorage.setItem('jhworks:manual-draft:emp_other', JSON.stringify({ content: '다른 계정 합성 요청', expiresAt: Date.now() + 60000 }));
  });
  await page.goto('/approvals/new?handoff=manual');
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toBeEmpty();
  expect(await page.evaluate(() => sessionStorage.getItem('jhworks:manual-draft:emp_sales_001'))).toBeNull();
  await page.evaluate(() => sessionStorage.setItem('jhworks:manual-draft:emp_sales_001', JSON.stringify({ content: '명시적 전환만 허용', expiresAt: Date.now() + 60000 })));
  await page.goto('/approvals/new');
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toBeEmpty();
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => sessionStorage.getItem('jhworks:manual-draft:emp_sales_001'))).toBeNull();
});

test('additional answers are carried literally without inferred facts', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill('다음 주 화요일 부산에서 열리는 CES 협력사 미팅 출장 신청을 준비해줘. 예상 교통비는 17만원이야.');
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  const answer = page.getByRole('textbox', { name: '추가 정보', exact: true });
  await expect(answer).toBeVisible();
  await answer.fill('당일 출장, 교통비 17만원');
  await page.route('**/approval-draft-assistant/prepare', (route) => route.fulfill({ status: 503, json: { error: { code: 'AI_DRAFT_UNAVAILABLE' } } }));
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await page.getByRole('button', { name: '직접 작성으로 계속 →' }).click();
  await expect(page.getByRole('textbox', { name: '업무 내용', exact: true })).toHaveValue('다음 주 화요일 부산에서 열리는 CES 협력사 미팅 출장 신청을 준비해줘. 예상 교통비는 17만원이야.\n\n당일 출장, 교통비 17만원');
});

test('an oversized transfer does not silently truncate the request', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'AI 초안 작성', exact: true }).click();
  const original = '합성'.repeat(1000);
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill(original);
  let turn = 0;
  await page.route('**/approval-draft-assistant/prepare', (route) => {
    turn++;
    return route.fulfill(turn <= 2 ? {
      json: { status: 'NEEDS_INPUT', intent: 'EXPENSE', questions: [{ field: 'expense_date', prompt: '합성 추가 질문' }], assistantMessage: '추가 정보를 입력해주세요.', preview: null, confirmationToken: null },
    } : { status: 503, json: { error: { code: 'AI_DRAFT_UNAVAILABLE' } } });
  });
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  const answer = page.getByRole('textbox', { name: '추가 정보', exact: true });
  await answer.fill('답변'.repeat(1000));
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await expect(answer).toBeEmpty();
  await answer.fill('보완'.repeat(1000));
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await page.getByRole('button', { name: '직접 작성으로 계속 →' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '전체 5,000자 한도' })).toBeVisible();
  await expect(page.getByText(original, { exact: true })).toBeVisible();
  await expect(answer).toHaveValue('보완'.repeat(1000));
  await expect(page).toHaveURL(/\/approvals\/ai-draft$/);
});
