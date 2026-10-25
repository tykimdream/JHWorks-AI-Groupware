import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';

const index = JSON.parse(readFileSync('apps/pattern-storybook/storybook-static/index.json', 'utf8'));
const ids = Object.keys(index.entries).filter((id) => index.entries[id].type === 'story');

for (const id of ids) {
  test(`static story ${id} renders and meets accessibility checks`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    let apiCalls = 0;
    page.on('request', (request) => { if (request.url().includes('/api/v1/')) apiCalls++; });
    await page.goto(`iframe.html?id=${id}&viewMode=story`);
    await expect(page.locator('#storybook-root')).not.toBeEmpty();
    await expect(page.locator('.sb-errordisplay')).not.toBeVisible();
    // Wait for fonts and network-loaded story chunks before scanning.
    await page.waitForLoadState('networkidle');
    if (id.endsWith('--validation')) {
      await expect(page.getByRole('textbox', { name: '업무 목적' })).toHaveValue('CES 합성 출장');
    }
    if (id.endsWith('--keyboard')) {
      await expect(page.getByRole('status')).toHaveText('합성 예제 확인 완료');
    }
    const axe = await new AxeBuilder({ page }).include('#storybook-root').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(axe.violations).toEqual([]);
    expect(errors).toEqual([]);
    expect(apiCalls).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('confirmation keyboard and pending behavior work from a static subpath', async ({ page }, testInfo) => {
  await page.goto('iframe.html?id=jhw-pattern-overlay-confirmation--default&viewMode=story');
  const trigger = page.getByRole('button', { name: '합성 확인 창 열기' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: '합성 초안을 제출할까요?' });
  await expect(dialog.getByRole('button', { name: '취소' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: '확인하고 제출' })).toBeFocused();
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  await mkdir('artifacts/storybook', { recursive: true });
  await page.screenshot({ path: `artifacts/storybook/confirmation-${testInfo.project.name}.png` });
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await page.goto('iframe.html?id=jhw-pattern-overlay-confirmation--pending&viewMode=story');
  await page.getByRole('button', { name: '합성 확인 창 열기' }).click();
  await expect(dialog.getByRole('button', { name: '취소' })).toBeDisabled();
  await expect(dialog.getByRole('button', { name: '처리 중…' })).toBeDisabled();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
});

test('static manager, brand asset and direct docs link resolve below /storybook/', async ({ page, request }, testInfo) => {
  const favicon = await request.get('favicon.svg');
  expect(favicon.ok()).toBe(true);
  expect(favicon.headers()['content-type']).toContain('image/svg+xml');
  expect(await favicon.text()).toBe(readFileSync('apps/web/src/app/icon.svg', 'utf8'));
  const brand = await request.get('brand/jhworks-wordmark.svg');
  expect(brand.ok()).toBe(true);
  expect(brand.headers()['content-type']).toContain('image/svg+xml');
  await page.goto('?path=/docs/jhw-pattern-forms-field--docs');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', './favicon.svg');
  await expect(page.locator('iframe#storybook-preview-iframe')).toBeVisible();
  await expect(page.frameLocator('iframe#storybook-preview-iframe').getByRole('heading', { name: 'Field', exact: true }).first()).toBeVisible();
  await page.reload();
  await expect(page.locator('iframe#storybook-preview-iframe')).toBeVisible();
  await expect(page.frameLocator('iframe#storybook-preview-iframe').getByRole('heading', { name: 'Field', exact: true }).first()).toBeVisible();
  await page.waitForLoadState('networkidle');
  await mkdir('artifacts/storybook', { recursive: true });
  await page.screenshot({ path: `artifacts/storybook/manager-${testInfo.project.name}.png` });
});
