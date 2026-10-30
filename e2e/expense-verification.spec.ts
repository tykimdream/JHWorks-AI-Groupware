import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function preview(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toBeVisible();
  await page.goto('/approvals/ai-draft');
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill('이번 CES 출장에서 쓴 17만원 경비 정산 결재를 준비해줘.');
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '추가 정보', exact: true })).toBeVisible();
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
  await page.getByRole('textbox', { name: '추가 정보', exact: true }).fill(`${today} 코레일 교통비 RCP-CES-001`);
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'CES 출장 경비 정산', exact: true })).toBeVisible();
}

test('expense verification separates input matches, rule actions and execution completion', async ({ page }) => {
  await preview(page);
  const region = page.getByRole('region', { name: '경비 초안 검증 결과', exact: true });
  await expect(region.getByText('입력과 일치', { exact: true })).toHaveCount(6);
  await expect(region.getByText('추가 확인 필요', { exact: true })).toBeVisible();
  await expect(region.getByText('자동 판정하지 않음', { exact: true })).toHaveCount(2);
  await expect(region).toContainText('참조 번호는 첨부·진위 확인을 대신하지 않습니다.');
  await region.getByText(/^근거:.*EXPENSE-2/).click();
  await expect(region.getByText('100,000원 이상의 경비에는 영수증이 필요합니다.', { exact: true })).toBeVisible();
  await region.getByText('검사 실행 정보', { exact: true }).click();
  await expect(region.getByText(/실행 ID: draft_run_/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(results.violations).toEqual([]);
});

test('legacy expense response without verification cannot be confirmed', async ({ page }) => {
  await page.route('**/approval-draft-assistant/prepare', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    delete body.grounding;
    delete body.execution;
    delete body.policyValidation;
    await route.fulfill({ response, json: body });
  });
  await preview(page);
  await expect(page.getByRole('button', { name: '확인하고 초안으로 저장', exact: true })).toBeDisabled();
  await expect(page.getByRole('alert').filter({ hasText: '경비 검증 정보가 없습니다' })).toBeVisible();
});

test('stale policy response preserves follow-up inputs for a new preparation', async ({ page }) => {
  await preview(page);
  await page.route('**/approval-draft-assistant/confirm', (route) => route.fulfill({
    status: 409, json: { error: { code: 'POLICY_CHANGED', message: 'changed' } },
  }));
  await page.getByRole('button', { name: '확인하고 초안으로 저장', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '규정이 변경되어' })).toBeVisible();
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'CES 출장 경비 정산', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '추가 정보', exact: true })).toHaveCount(0);
});
