import { expect, test } from '@playwright/test';

test('natural keyword phrase finds lodging policy', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await page.goto('/policies');
  await page.getByLabel('규정 검색').fill('숙박 관련');
  await expect(page.getByText('일치하는 규정이 없습니다')).toHaveCount(0);
  await expect(page.locator('article').first()).toBeVisible();
});
