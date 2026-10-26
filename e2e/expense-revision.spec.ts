import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

async function login(page: Page, manager = false) {
  await page.goto('/login');
  if (manager) await page.getByRole('button', { name: /결재자 · 최도윤/ }).click();
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.locator('.profile-card')).toContainText(manager ? '최도윤' : '윤서진');
}
async function post(page: Page, path: string, data: unknown) {
  const response = await page.request.post(`/api/v1${path}`, { data, headers: { Origin: 'http://localhost:3100' } });
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}

test('approver evidence → rejection → grounded correction diff → same draft → resubmit', async ({ page }, info) => {
  await login(page);
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
  const item = await post(page, '/approvals', {
    type: 'EXPENSE', title: `반려 보완 검증 ${info.project.name}`, content: 'CES 출장 경비', amount: 170000,
    details: { kind: 'EXPENSE', expenseDate: today, merchant: '코레일', category: 'TRANSPORTATION', purpose: 'CES 출장', receiptReference: 'RCP-CES-001' },
  });
  const pending = await post(page, `/approvals/${item.id}/submit`, { version: item.version });
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await login(page, true);
  await page.goto(`/approvals/${item.id}`);
  const brief = page.getByRole('region', { name: '결재자 경비 검토 요약' });
  await expect(brief.getByText('추가 확인 필요', { exact: true })).toBeVisible();
  await expect(brief).toContainText('원본 첨부·진위는 확인되지 않았습니다.');
  await brief.getByText('근거: Receipts · 1.0', { exact: true }).click();
  await expect(brief).toContainText('Expenses of KRW 100,000 or more require a receipt.');
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({ path: `artifacts/workspace-preview/decision-brief-${info.project.name}.png`, fullPage: true });
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  await page.getByLabel('결재 의견').fill('업무 목적을 구체적으로 적고 영수증 원본을 확인해 주세요.');
  await page.getByRole('button', { name: '반려', exact: true }).click();
  await page.getByRole('dialog', { name: '결재 반려 확인' }).getByRole('button', { name: '확인하고 반려' }).click();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('반려');
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await login(page);
  await page.goto(`/approvals/${item.id}`);
  const revision = page.getByRole('region', { name: '반려 경비 AI 수정 제안' });
  await revision.getByLabel('보완할 실제 사실').fill('목적: CES 협력사 데모 시연');
  await revision.getByRole('button', { name: '반려 의견으로 AI 수정 제안 준비', exact: true }).click();
  await expect(revision.getByRole('heading', { name: '변경 전후를 확인하세요' })).toBeVisible();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('반려');
  await expect(revision).toContainText('CES 협력사 데모 시연');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({ path: `artifacts/workspace-preview/expense-revision-${info.project.name}.png`, fullPage: true });
  await revision.getByRole('button', { name: '변경 확인 후 같은 문서의 초안에 반영', exact: true }).click();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('초안');
  await expect(page.locator('.expense-summary')).toContainText('CES 협력사 데모 시연');
  await expect(page).toHaveURL(new RegExp(`/approvals/${item.id}$`));
  await page.getByRole('button', { name: '제출', exact: true }).click();
  await page.getByRole('dialog', { name: '결재 제출 확인' }).getByRole('button', { name: '확인하고 제출' }).click();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('결재 대기');
  const final = await page.request.get(`/api/v1/approvals/${item.id}`);
  const saved = await final.json();
  expect(saved.lines).toHaveLength(2);
  expect(saved.version).toBe(pending.version + 3);
});
