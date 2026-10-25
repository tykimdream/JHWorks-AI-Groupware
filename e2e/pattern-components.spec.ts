import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test('shared field connects label, help and errors without calling the business API', async ({ page }, testInfo) => {
  let writes = 0;
  page.on('request', (request) => { if (request.method() !== 'GET' && request.url().includes('/api/v1/')) writes++; });
  await page.goto('/pattern');
  const amount = page.getByRole('spinbutton', { name: '실제 지출 금액', exact: true });
  await expect(amount).toHaveAccessibleDescription('이미 지출한 금액을 원 단위로 입력합니다.');
  await expect(amount).toHaveAttribute('required', '');
  await page.getByRole('button', { name: '입력 조건 확인', exact: true }).click();
  await expect(amount).toHaveAttribute('aria-invalid', 'true');
  await expect(amount).toHaveAccessibleDescription(/0원보다 큰 금액/);
  await amount.fill('170000');
  await expect(amount).not.toHaveAttribute('aria-invalid');
  await expect(amount).toHaveAccessibleDescription('이미 지출한 금액을 원 단위로 입력합니다.');
  await page.getByRole('combobox', { name: '비용 구분', exact: true }).selectOption('TRANSPORTATION');
  await page.getByRole('textbox', { name: '업무 목적', exact: true }).fill('합성 예제');
  await page.getByRole('button', { name: '예제 다시 시도', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '예제 재시도가 완료됐습니다' })).toBeVisible();
  expect(writes).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await mkdir('artifacts/pattern', { recursive: true });
  await page.screenshot({ path: `artifacts/pattern/forms-${testInfo.project.name}.png` });
});

test('shared confirmation cancels, traps footer focus and restores its trigger', async ({ page }) => {
  await page.goto('/pattern');
  const trigger = page.getByRole('button', { name: '확인 창 예제 열기', exact: true });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: '예제 초안을 제출할까요?' });
  await expect(dialog.getByRole('button', { name: '취소', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: '예제 확인', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: '취소', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await dialog.getByRole('button', { name: '예제 확인', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('status').filter({ hasText: '예제 확인을 완료했습니다' })).toBeVisible();
});
