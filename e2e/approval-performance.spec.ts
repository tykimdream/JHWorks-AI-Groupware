import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { arch, platform, release } from 'node:os';

// Measurements are descriptive, not latency assertions. No external service or production data.
test('measure authenticated list HTTP and current rendered page', async ({ page, browser }, testInfo) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');

  const sample = async (path: string) => page.evaluate(async (url) => {
    const start = performance.now();
    const response = await fetch(url, { cache: 'no-store' });
    const bytes = await response.arrayBuffer();
    const end = performance.now();
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = JSON.parse(new TextDecoder().decode(bytes));
    return { ms: end - start, bytes: bytes.byteLength, rows: data.items.length, total: data.total };
  }, path);
  const paths = ['/api/v1/approvals?scope=mine', '/api/v1/approvals/summaries?scope=mine&limit=20&offset=0'];
  const results = [];
  for (const path of paths) {
    await sample(path);
    const samples = [];
    for (let i = 0; i < 5; i++) samples.push(await sample(path));
    expect(samples.every((s) => s.total >= 1000)).toBe(true);
    expect(samples.every((s) => s.rows === (path.includes('summaries') ? 20 : s.total))).toBe(true);
    results.push({ endpoint: path.includes('summaries') ? 'summary' : 'legacy', samples });
  }
  const renders = [];
  for (let i = 0; i < 6; i++) {
    const start = performance.now();
    await page.goto('/approvals?scope=mine');
    await expect(page.locator('.approval-row')).toHaveCount(20);
    const ms = performance.now() - start;
    if (i > 0) renders.push(ms);
  }
  await mkdir('artifacts/performance', { recursive: true });
  await writeFile(`artifacts/performance/approval-http-browser-${testInfo.project.name}.json`, JSON.stringify({
    fixture: 'sqlite-1000-mine', browser: testInfo.project.name, warmup: 1,
    browserVersion: browser.version(), nodeVersion: process.version,
    platform: `${platform()} ${release()} ${arch()}`,
    http: results, navigationTo20RowsMs: renders,
  }, null, 2));
});
