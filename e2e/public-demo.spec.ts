import { expect, test, type Page } from '@playwright/test';

async function verifyDesktopLayout(page: Page) {
  for (const width of [1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const sidebar = await page.locator('.sidebar').boundingBox();
    expect(Math.abs(sidebar!.y)).toBeLessThan(1);
    expect(sidebar?.height).toBeCloseTo(900, 0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.getByRole('link', { name: 'JHWorks 홈으로', exact: true })).toBeVisible();
  }
  // A short laptop viewport must keep account actions visible while only the menu scrolls.
  for (const height of [600, 720, 900]) {
    await page.setViewportSize({ width: 1280, height });
    const sidebar = page.locator('.sidebar');
    const footer = sidebar.locator('.sidebar-footer');
    const footerBox = await footer.boundingBox();
    const navBox = await sidebar.getByRole('navigation', { name: '주 메뉴' }).boundingBox();
    const profile = await footer.locator('.profile-card').boundingBox();
    const role = await footer.getByRole('button', { name: /결재자로 체험하기|작성자로 돌아가기/ }).boundingBox();
    expect(footerBox!.y + footerBox!.height).toBeLessThanOrEqual(height - 15);
    expect(navBox!.y + navBox!.height).toBeLessThanOrEqual(footerBox!.y);
    expect(role!.y + role!.height + 15).toBeLessThanOrEqual(profile!.y);
    expect(await sidebar.evaluate((node) => getComputedStyle(node).borderTopWidth)).toBe('0px');
    expect(await footer.evaluate((node) => getComputedStyle(node).borderLeftWidth)).toBe('0px');
    await expect(footer.getByRole('button', { name: '로그아웃', exact: true })).toBeInViewport();
    if (height === 600) await page.screenshot({ path: `artifacts/workspace-preview/sidebar-short-${new URL(page.url()).pathname === '/' ? 'home' : 'detail'}.png`, style: 'nextjs-portal { display: none; }' });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}


test('real public visitor can switch roles, approve, and leave one private feedback', async ({ page }, testInfo) => {
  // Real API/domain/isolated SQLite. No routes are mocked and no paid AI is called.
  await page.goto('/login');
  await expect(page.getByRole('button', { name: '체험 시작하기' })).toBeVisible();
  await expect(page.getByLabel('비밀번호')).toHaveCount(0);
  await page.getByRole('button', { name: '체험 시작하기' }).click();
  await expect(page).toHaveURL('http://localhost:3100/');
  await expect(page.getByRole('textbox', { name: 'AI 업무 요청' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'AI 초안 작성으로 이동' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'AI 초안 작성', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '결재자로 체험하기' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '경비 정산부터 시작해 보세요' })).toBeVisible();
  await page.getByRole('button', { name: '사용 가이드 닫기', exact: true }).click();
  const original = await (await page.request.get('/api/v1/employees/me')).json();
  expect(original.id).toMatch(/^demo_author_/);
  if (testInfo.project.name === 'desktop') await verifyDesktopLayout(page);
  else {
    await expect(page.locator('.nav-caption').first()).toBeHidden();
    expect((await page.getByRole('navigation', { name: '주 메뉴' }).boundingBox())!.height).toBeLessThan(60);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `docs/portfolio/screenshots/public-home-${testInfo.project.name}.png`, style: 'nextjs-portal { display: none; }' });
  await page.goto('/approvals/new');
  await page.getByLabel('결재 종류').selectOption('EXPENSE');
  const title = 'CES 출장 교통비 17만원 정산';
  await page.getByLabel('제목', { exact: true }).fill(title);
  await page.getByLabel('업무 내용').fill('CES 고객 미팅을 위한 교통비를 정산합니다.');
  await page.getByLabel('실제 지출 금액 (원)').fill('170000');
  await page.getByLabel('실제 지출일').fill('2026-01-08');
  await page.getByLabel('사용처').fill('코레일');
  await page.getByLabel('비용 구분').selectOption('TRANSPORTATION');
  await page.getByLabel('업무상 지출 목적').fill('CES 고객 미팅 참석을 위한 이동');
  await page.getByLabel('증빙 참조 (선택)').fill('RCP-CES-001');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/approvals\/apr_[^/]+$/);
  const id = new URL(page.url()).pathname.split('/').at(-1);
  const path = '/api/v1/approvals/' + id;
  const badge = page.locator('.detail-title-row .status-badge');
  await expect(badge).toHaveText('초안');
  await expect(page.getByText('공개 체험에서는 AI 검토를 제공하지 않습니다.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI로 검토하기', exact: true })).toHaveCount(0);
  let submitRequests = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === path + '/submit') submitRequests += 1;
  });
  const submit = page.getByRole('button', { name: '제출', exact: true });
  await submit.click();
  const confirmation = page.getByRole('dialog', { name: '결재 제출 확인' });
  await expect(confirmation).toContainText(title);
  await expect(confirmation).toContainText('170,000');
  await expect(confirmation).toContainText('v1');
  await page.screenshot({ path: `artifacts/workspace-preview/approval-confirm-${testInfo.project.name}.png`, style: 'nextjs-portal { display: none; }' });
  await expect(confirmation.getByRole('button', { name: '취소', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(confirmation.getByRole('button', { name: '확인하고 제출' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(confirmation.getByRole('button', { name: '취소', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(confirmation).not.toBeVisible();
  await expect(submit).toBeFocused();
  await expect(badge).toHaveText('초안');
  expect(submitRequests).toBe(0);
  await submit.click();
  await page.keyboard.press('Escape');
  await expect(confirmation).not.toBeVisible();
  expect((await (await page.request.get(path)).json()).status).toBe('DRAFT');
  expect(submitRequests).toBe(0);
  await submit.click();
  await confirmation.getByRole('button', { name: '확인하고 제출' }).click();
  await expect(badge).toHaveText('결재 대기');
  expect(submitRequests).toBe(1);
  await page.getByRole('link', { name: '업무 홈', exact: true }).click();
  const nextAction = page.getByRole('complementary').filter({ hasText: '다음 할 일' });
  await expect(nextAction).toContainText(title);
  await expect(nextAction).toContainText('결재를 기다리는 문서가 있어요');
  await nextAction.getByRole('link', { name: '문서 확인하기' }).click();
  await page.getByRole('region', { name: '체험 다음 단계' }).getByRole('button', { name: '결재자로 전환해 계속하기' }).click();
  await expect(page.getByRole('button', { name: '작성자로 돌아가기' })).toBeVisible();
  const manager = await (await page.request.get('/api/v1/employees/me')).json();
  expect(manager.id).toBe(original.manager.id);
  await page.getByRole('tab', { name: '내게 배정된 문서' }).click();
  await page.getByRole('link').filter({ hasText: title }).click();
  await expect(badge).toHaveText('결재 대기');
  await page.getByLabel('결재 의견').fill('업무 목적과 증빙 참조를 확인했습니다.');
  await page.getByRole('button', { name: '승인', exact: true }).click();
  const approve = page.getByRole('dialog', { name: '결재 승인 확인' });
  await expect(approve).toContainText('업무 목적과 증빙 참조를 확인했습니다.');
  await approve.getByRole('button', { name: '확인하고 승인' }).click();
  await expect(badge).toHaveText('승인');
  expect((await (await page.request.get(path)).json()).status).toBe('APPROVED');
  await page.evaluate(() => window.scrollTo(0, 0));
  if (testInfo.project.name === 'desktop') await verifyDesktopLayout(page);
  await page.screenshot({ path: `docs/portfolio/screenshots/public-expense-approved-${testInfo.project.name}.png`, style: 'nextjs-portal { display: none; }' });
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


test('public Swagger renders the real schema with execution disabled', async ({ page }, testInfo) => {
  const response = await page.request.get('/api/v1/docs');
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain('"supportedSubmitMethods": []');
  await page.goto('/api/v1/docs');
  await expect(page.locator('.swagger-ui .info .title')).toContainText('JHWorks API');
  await expect(page.locator('.swagger-ui .opblock-tag').filter({ hasText: '전자결재' })).toBeVisible();
  const domains = ['전자결재', '근태·휴가', '정책', '조직', '업무 도우미', '인증·체험', '운영'];
  await expect(page.locator('.swagger-ui .opblock-tag')).toHaveCount(domains.length);
  for (const domain of domains) {
    await page.locator('.swagger-ui .opblock-tag').filter({ hasText: domain }).click();
  }
  const schemaResponse = await page.request.get('/api/v1/openapi.json');
  expect(schemaResponse.ok()).toBe(true);
  const schema = await schemaResponse.json();
  const methods = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']);
  const operationCount = Object.values(schema.paths as Record<string, Record<string, unknown>>)
    .reduce((total, path) => total + Object.keys(path).filter((method) => methods.has(method)).length, 0);
  expect(operationCount).toBeGreaterThan(0);
  await expect(page.locator('.swagger-ui .opblock')).toHaveCount(operationCount);
  for (const suffix of ['decision-brief', 'expense-revision/prepare', 'expense-revision/apply']) {
    await expect(page.locator('.swagger-ui .opblock-summary').filter({ hasText: `/api/v1/approvals/{approval_id}/${suffix}` })).toHaveCount(1);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('.swagger-ui .opblock-summary').filter({ hasText: '/api/v1/approvals' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Try it out', exact: true })).toHaveCount(0);
  await page.screenshot({ path: `artifacts/workspace-preview/swagger-public-${testInfo.project.name}.png`, fullPage: true, style: 'nextjs-portal { display: none; }' });
});


test('first visitor guide can be dismissed, remembered and reopened without creating a document', async ({ page }, testInfo) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '체험 시작하기', exact: true }).click();
  const guide = page.getByRole('dialog', { name: '경비를 초안으로 저장해요' });
  await expect(guide).toBeVisible();
  await page.screenshot({ path: `artifacts/workspace-preview/welcome-guide-${testInfo.project.name}.png`, style: 'nextjs-portal { display: none; }' });
  await guide.getByRole('button', { name: '나중에 볼게요' }).click();
  await expect(guide).not.toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '경비 정산부터 시작해 보세요' })).toBeVisible();
  await expect(page.locator('.guide-card')).toHaveCount(0);
  await page.getByRole('button', { name: '사용 가이드', exact: true }).click();
  await expect(page.getByRole('button', { name: '사용 가이드 닫기' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('.guide-card')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '사용 가이드', exact: true })).toBeFocused();
  await page.getByRole('button', { name: '사용 가이드', exact: true }).click();
  await page.locator('.guide-card').getByRole('button', { name: '다음', exact: true }).click();
  await expect(page.getByRole('heading', { name: '내용을 확인하고 제출해요' })).toBeVisible();
  await page.locator('.guide-card').getByRole('button', { name: '다음', exact: true }).click();
  let writes = 0;
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/approvals') writes += 1; });
  await page.locator('.guide-card').getByRole('link', { name: '경비 정산 시작' }).click();
  await expect(page.getByLabel('결재 종류')).toHaveValue('EXPENSE');
  expect(writes).toBe(0);
});

test('first visitor can dismiss the guide even when browser storage is unavailable', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage disabled for regression'); } }); });
  await page.goto('/login');
  await page.getByRole('button', { name: '체험 시작하기', exact: true }).click();
  await page.getByRole('button', { name: '사용 가이드 닫기' }).click();
  await expect(page.locator('.guide-card')).toHaveCount(0);
  await page.getByRole('button', { name: '사용 가이드', exact: true }).click();
  await expect(page.locator('.guide-card')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.guide-card')).toHaveCount(0);
  await page.getByRole('link', { name: '경비 정산 시작', exact: true }).click();
  await expect(page.getByLabel('결재 종류')).toHaveValue('EXPENSE');
});

test('JHW Pattern is public, searchable and uses keyboard-accessible help', async ({ page }, testInfo) => {
  await page.goto('/pattern');
  await expect(page.getByRole('heading', { name: /좋은 업무 흐름을 만드는/ })).toBeVisible();
  await page.getByLabel('패턴 검색').fill('--jhw-color-primary');
  await expect(page.getByRole('status').filter({ hasText: '토큰 3개' })).toBeVisible();
  await page.getByLabel('패턴 검색').fill('');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '업무 데이터는 변경되지 않습니다' })).toBeVisible();
  const hint = page.getByRole('button', { name: '초안과 제출의 차이', exact: true });
  await hint.focus();
  await expect(page.getByRole('tooltip')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  await expect(hint).toBeFocused();
  await page.getByText('코드 보기 · Button', { exact: true }).click();
  await expect(page.getByRole('button', { name: '코드 복사 · Button', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `artifacts/workspace-preview/jhw-pattern-${testInfo.project.name}.png`, style: 'nextjs-portal { display: none; }' });
});

test('public demo expense help works with AI off and keeps the form intact', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '체험 시작하기', exact: true }).click();
  await expect(page.locator('.profile-card')).toBeVisible();
  const welcome = page.getByRole('dialog', { name: '경비를 초안으로 저장해요' });
  if (await welcome.isVisible()) await welcome.getByRole('button', { name: '나중에 볼게요' }).click();
  await page.goto('/approvals/new?type=EXPENSE');
  await page.getByLabel('제목', { exact: true }).fill('공개 도움말 입력 보존');
  let writes = 0;
  page.on('request', (request) => { if (['POST', 'PATCH', 'DELETE'].includes(request.method())) writes++; });
  await page.getByRole('button', { name: '경비 업무 도움말', exact: true }).click();
  const help = page.getByRole('dialog', { name: '경비 업무 도움말', exact: true });
  await help.getByRole('button', { name: '누가 승인하고 어떤 것을 확인하나요?', exact: true }).click();
  await expect(help.getByRole('status').filter({ hasText: '직속 관리자가 결재자로 지정됩니다.' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('제목', { exact: true })).toHaveValue('공개 도움말 입력 보존');
  expect(writes).toBe(0);
});
