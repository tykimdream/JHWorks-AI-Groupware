import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test('CES actual expense → missing facts → policy preview → save → edit → submit → manager approval', async ({
  page,
}, testInfo) => {
  const duplicateKeyErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('same key')) duplicateKeyErrors.push(message.text());
  });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await page.getByRole('textbox', { name: 'AI 업무 요청' }).fill('이번 CES 출장에서 쓴 17만원 경비 정산 결재를 준비해줘.');
  await page.getByRole('button', { name: 'AI 초안 작성으로 이동', exact: true }).click();
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(
    page.getByText('어느 사용처에 지출했나요? 상호 또는 결제 대상을 알려주세요.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'CES 출장 경비 정산', exact: true })).toHaveCount(
    0,
  );
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
  await page
    .getByRole('textbox', { name: '추가 정보', exact: true })
    .fill(`${today} 코레일에서 쓴 교통비야. 증빙 참조는 RCP-CES-001이야.`);
  await page.getByRole('button', { name: '답변 반영', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'CES 출장 경비 정산', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.expense-summary')).toContainText('170,000');
  await expect(page.locator('.expense-summary')).toContainText('코레일');
  await expect(page.locator('.draft-policy-card')).toContainText('Receipts');
  await expect(page.locator('.expense-summary')).toContainText('원본 검증은 지원하지 않으며');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await mkdir('artifacts/workspace-preview', { recursive: true });
  await page.screenshot({
    path: `artifacts/workspace-preview/expense-preview-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole('button', { name: '확인하고 초안으로 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/?]+\/edit$/);
  await expect(page.getByLabel('결재 종류')).toHaveValue('EXPENSE');
  await expect(page.getByLabel('실제 지출 금액 (원)')).toHaveValue('170,000');
  await page.getByLabel('사용처', { exact: true }).fill('코레일 서울역');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page.locator('.expense-summary')).toContainText('코레일 서울역');
  await page.getByRole('button', { name: '제출', exact: true }).click();
  await page.getByRole('dialog', { name: '결재 제출 확인' }).getByRole('button', { name: '확인하고 제출' }).click();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('결재 대기');
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await page.getByRole('button', { name: /결재자 · 최도윤/ }).click();
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page.getByRole('heading', { name: /검토할 결재/ })).toBeVisible();
  await expect(page.getByRole('link', { name: '결재 검토하기' })).toHaveAttribute('href', /from=assigned/);
  await page.getByRole('link', { name: /내가 처리할 결재/ }).click();
  await page.locator('.approval-row').filter({ hasText: 'CES 출장 경비 정산' }).first().click();
  await expect(page.locator('.expense-summary')).toContainText('RCP-CES-001');
  await page.getByRole('button', { name: '승인', exact: true }).click();
  await page.getByRole('dialog', { name: '결재 승인 확인' }).getByRole('button', { name: '확인하고 승인' }).click();
  await expect(page.locator('.detail-title-row .status-badge')).toContainText('승인');
  await expect(page.getByRole('button', { name: '경비 업무 도움말' })).toHaveCount(1);
  expect(duplicateKeyErrors).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `artifacts/workspace-preview/expense-approved-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
