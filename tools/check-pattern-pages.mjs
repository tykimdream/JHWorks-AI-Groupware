// Read-only smoke for the approved static Pages site. No product API calls.
import { fileURLToPath } from 'node:url';
import { chromium, expect, devices } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
const base = 'https://tykimdream.github.io/JHWorks-AI-Groupware/';
const output = fileURLToPath(new URL('../artifacts/storybook/public/', import.meta.url));
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [];
try {
  for (const [name, options] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['mobile', { ...devices['iPhone 13'], defaultBrowserType: undefined }]]) {
    const context = await browser.newContext(options);
    const page = await context.newPage();
    const errors = [], apiCalls = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', request => { if (request.url().includes('/api/v1/')) apiCalls.push(request.url()); });
    const index = await context.request.get(base + 'index.json');
    expect(index.ok()).toBe(true);
    const entries = (await index.json()).entries;
    expect(Object.values(entries).filter(x => x.type === 'story')).toHaveLength(23);
    const brand = await context.request.get(base + 'brand/jhworks-wordmark.svg');
    expect(brand.ok()).toBe(true);
    expect(brand.headers()['content-type']).toContain('image/svg+xml');
    const response = await page.goto(base + '?path=/docs/jhw-pattern-forms-field--docs');
    expect(response.status()).toBe(200);
    const preview = page.frameLocator('#storybook-preview-iframe');
    await expect(preview.getByRole('heading', { name: 'Field', exact: true }).first()).toBeVisible();
    await page.reload();
    await expect(preview.getByRole('heading', { name: 'Field', exact: true }).first()).toBeVisible();
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${output}/manager-${name}.png` });
    await page.goto(base + 'iframe.html?id=jhw-pattern-forms-field--required&viewMode=story');
    await expect(page.getByLabel('실제 지출 금액', { exact: true })).toBeVisible();
    await expect(page.getByLabel('실제 지출 금액', { exact: true })).toHaveAttribute('required', '');
    await page.goto(base + 'iframe.html?id=jhw-pattern-overlay-confirmation--default&viewMode=story');
    const trigger = page.getByRole('button', { name: '합성 확인 창 열기' });
    await trigger.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('button', { name: '취소' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(dialog.getByRole('button', { name: '확인하고 제출' })).toBeFocused();
    await page.screenshot({ path: `${output}/confirmation-${name}.png` });
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    await page.goto(base + 'iframe.html?id=jhw-pattern-overlay-confirmation--pending&viewMode=story');
    await page.getByRole('button', { name: '합성 확인 창 열기' }).click();
    await expect(page.getByRole('button', { name: '처리 중…' })).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(errors).toEqual([]);
    expect(apiCalls).toEqual([]);
    results.push({ viewport: name, dimensions: page.viewportSize(), stories: 23, docsReload: true, brand: true, requiredLabel: true, keyboard: true, pendingEscape: true, apiCalls: 0, pageErrors: 0 });
    await context.close();
  }
  await writeFile(`${output}/smoke.json`, JSON.stringify({ base, checkedAt: new Date().toISOString(), results }, null, 2) + '\n');
  console.log(JSON.stringify(results));
} finally { await browser.close(); }
