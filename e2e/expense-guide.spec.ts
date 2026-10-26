import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

async function login(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText('윤서진');
}

test('expense help preserves input, traps focus, answers questions and jumps to a field without writes', async ({ page }, info) => {
  await login(page);
  await page.goto('/approvals/new?type=EXPENSE');
  await page.getByLabel('제목', { exact: true }).fill('도움말 보존 확인');
  let writes = 0;
  page.on('request', (request) => { if (['POST', 'PATCH', 'DELETE'].includes(request.method())) writes++; });
  const trigger = page.getByRole('button', { name: '경비 업무 도움말', exact: true });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: '경비 업무 도움말', exact: true });
  await expect(dialog.getByText('서버 업무 계약에 따른 안내입니다.', { exact: false })).toBeVisible();
  await expect(dialog).toContainText('새 문서의 입력값은 검사하거나 전송하지 않습니다.');
  await expect(dialog.getByRole('button', { name: '닫기', exact: true })).toBeFocused();
  await dialog.getByRole('button', { name: '저장과 제출은 어떻게 다른가요?', exact: true }).click();
  await expect(dialog.getByRole('status').filter({ hasText: '초안 저장은' })).toBeVisible();
  await dialog.getByRole('button', { name: '증빙 참조만 적으면 영수증이 확인되나요?', exact: true }).click();
  await expect(dialog.getByRole('status').filter({ hasText: '파일 업로드·원본 진위 검증은 제공하지 않습니다.' })).toBeVisible();
  expect(await page.evaluate(() => document.querySelector('dialog')!.scrollWidth <= document.querySelector('dialog')!.clientWidth)).toBe(true);
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({ path: `artifacts/workspace-preview/expense-guide-${info.project.name}.png` });
  await dialog.getByRole('button', { name: '닫기', exact: true }).focus();
  await page.keyboard.press('Shift+Tab');
  expect(await page.evaluate(() => !!document.activeElement?.closest('dialog'))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await expect(page.getByLabel('제목', { exact: true })).toHaveValue('도움말 보존 확인');
  await trigger.click();
  await dialog.getByRole('button', { name: '업무 목적 입력으로 이동', exact: true }).click();
  await expect(page.getByLabel('업무상 지출 목적', { exact: true })).toBeFocused();
  expect(writes).toBe(0);
});

test('saved document help marks missing fields and rejects stale check results', async ({ page }) => {
  await login(page);
  const response = await page.request.post('/api/v1/approvals', { headers: { Origin: 'http://localhost:3100' }, data: {
    type: 'EXPENSE', title: '도움말 저장본', content: '', amount: null, details: { kind: 'EXPENSE' },
  } });
  expect(response.ok()).toBe(true);
  const item = await response.json();
  await page.goto(`/approvals/${item.id}`);
  await page.getByRole('button', { name: '경비 업무 도움말', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '경비 업무 도움말', exact: true });
  await expect(dialog).toContainText('보완이 필요한 경비 필드가 있습니다.');
  await expect(dialog.getByText('실제 지출 금액 · 필수 · 보완 필요', { exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.route('**/expense-checks', async (route) => {
    const result = await route.fetch();
    await route.fulfill({ response: result, json: { ...await result.json(), version: item.version + 1 } });
  });
  await page.getByRole('button', { name: '경비 업무 도움말', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('저장된 문서가 바뀌었습니다.');
  await expect(dialog).not.toContainText('필수 경비 필드가 입력됐습니다.');
});

test('help loading failure is explicit and can be retried', async ({ page }) => {
  await login(page);
  await page.goto('/approvals/new?type=EXPENSE');
  await page.route('**/approvals/expense-guide', (route) => route.fulfill({ status: 503, json: { error: { code: 'HELP_UNAVAILABLE', message: '안내 연결 실패' } } }));
  await page.getByRole('button', { name: '경비 업무 도움말', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '경비 업무 도움말', exact: true });
  await expect(dialog.getByRole('alert')).toContainText('안내 연결 실패');
  await page.unroute('**/approvals/expense-guide');
  await dialog.getByRole('button', { name: '안내 다시 조회', exact: true }).click();
  await expect(dialog).toContainText('궁금한 것을 선택하세요');
  await expect(dialog.getByRole('alert')).toHaveCount(0);
});
