import { expect, test } from '@playwright/test';

test('real public visitor can switch roles, approve, and leave one private feedback', async ({ page }) => {
  // Real API/domain/isolated SQLite. No routes are mocked and no paid AI is called.
  await page.goto('/login');
  await expect(page.getByRole('button', { name: '체험 시작하기' })).toBeVisible();
  await expect(page.getByLabel('비밀번호')).toHaveCount(0);
  await page.getByRole('button', { name: '체험 시작하기' }).click();
  await expect(page).toHaveURL(/\/approvals$/);
  await expect(page.getByRole('button', { name: '결재자로 체험하기' })).toBeVisible();
  const original = await (await page.request.get('/api/v1/employees/me')).json();
  expect(original.id).toMatch(/^demo_author_/);
  const created = await page.request.post('/api/v1/approvals', { data: {
    type: 'GENERAL', title: 'Synthetic public browser workflow',
    content: 'Independent synthetic demo content.', details: { kind: 'GENERAL' },
  } });
  expect(created.status()).toBe(201);
  const approval = await created.json();
  const path = '/api/v1/approvals/' + approval.id;
  const submitted = await page.request.post(path + '/submit', { data: { version: approval.version } });
  expect(submitted.status()).toBe(200);
  await page.getByRole('button', { name: '결재자로 체험하기' }).click();
  await expect(page.getByRole('button', { name: '작성자로 돌아가기' })).toBeVisible();
  const manager = await (await page.request.get('/api/v1/employees/me')).json();
  expect(manager.id).toBe(original.manager.id);
  const assigned = await (await page.request.get('/api/v1/approvals?scope=assigned')).json();
  expect(assigned.items.some((item: { id: string }) => item.id === approval.id)).toBe(true);
  const approved = await page.request.post(path + '/approve', { data: { version: (await submitted.json()).version } });
  expect(approved.status()).toBe(200);
  expect((await approved.json()).status).toBe('APPROVED');
  await page.getByRole('button', { name: '작성자로 돌아가기' }).click();
  await expect(page.getByRole('button', { name: '결재자로 체험하기' })).toBeVisible();
  expect((await (await page.request.get('/api/v1/employees/me')).json()).id).toBe(original.id);
  await page.getByRole('link', { name: '의견 남기기' }).click();
  const message = '합성 브라우저 검증 의견입니다. 역할 전환과 승인 작업을 완료했습니다.';
  await page.getByLabel('의견', { exact: true }).fill(message);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: '의견 보내기' }).click();
  await expect(page.getByRole('heading', { name: '의견을 접수했습니다' })).toBeVisible();
  const receipt = await page.locator('code').innerText();
  expect(receipt).toMatch(/^feedback_/);
  const again = await page.request.post('/api/v1/demo/feedback', { data: {
    category: 'usability', screen: 'general', message, consent: true,
  } });
  expect(again.status()).toBe(200);
  expect((await again.json()).id).toBe(receipt);
  expect((await page.request.get('/api/v1/demo/feedback')).status()).toBe(405);
});
