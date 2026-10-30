import { expect, test } from '@playwright/test';

test('general draft displays example body and accepts additional facts', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await page.route('**/api/v1/approval-draft-assistant/prepare', async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.exampleStatus = 'READY';
    data.examples = [{
      id: 'synthetic',
      title: '업무 협조 예시',
      outline: ['요청 배경', '협조 내용', '일정'],
      content: '1. 요청 배경\n[업무]를 위해 협조를 요청드립니다.',
    }];
    await route.fulfill({ response, json: data });
  });
  await page.goto('/approvals/ai-draft');
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill('전시 부스 제작 협조 요청');
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByText('업무 협조 예시', { exact: true })).toBeVisible();
  await page.getByText('가상 예시 본문 보기', { exact: true }).click();
  await expect(page.getByText('[업무]를 위해 협조를 요청드립니다.', { exact: false })).toBeVisible();
  await page.getByRole('textbox', { name: '추가하거나 정정할 내용' }).fill('일정은 다음 주입니다.');
  const updated = page.waitForResponse((response) =>
    response.url().endsWith('/approval-draft-assistant/prepare') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: '추가 내용 반영', exact: true }).click();
  await updated;
  await expect(page.getByRole('button', { name: '추가 내용 반영', exact: true })).toBeDisabled();
  await expect(page.getByText('일정은 다음 주입니다.', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('structured general draft shows the exact source for each fact', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await page.goto('/approvals/ai-draft');
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill([
    '문서 유형: 일반',
    '제목: 가상 협조 요청',
    '개요: 전시 부스 제작 협조를 요청합니다.',
    '업무 내용: 가상팀과 도면을 검토했습니다.',
  ].join('\n'));
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByRole('heading', { name: '가상 협조 요청', exact: true })).toBeVisible();
  await expect(page.getByText('기안 내용의 입력 근거', { exact: true })).toBeVisible();
  await expect(page.locator('.policy-citation').filter({ hasText: '가상팀과 도면을 검토했습니다.' })).toBeVisible();
  await expect(page.getByText('실제 사실과 맥락은 직접 확인해 주세요.', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('natural request preserves facts and shows any wording change', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await page.goto('/approvals/ai-draft');
  await page.getByRole('textbox', { name: '업무 요청', exact: true }).fill(
    '전시 부스 제작 협조를 요청했어. 가상팀과 도면을 검토했어.',
  );
  await page.getByRole('button', { name: 'AI로 초안 준비', exact: true }).click();
  await expect(page.getByText('입력 문장에 근거한 기안', { exact: true })).toBeVisible();
  await expect(page.locator('.draft-preview-card')).toContainText('가상팀과 도면을 검토했습니다.');
  const evidence = page.locator('.policy-citation').filter({ hasText: '가상팀과 도면을 검토했어.' });
  await expect(evidence).toContainText('기안: 가상팀과 도면을 검토했습니다.');
});
