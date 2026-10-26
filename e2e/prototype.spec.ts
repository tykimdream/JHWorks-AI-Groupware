import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function enter(page: Page) {
  const configuration = await (
    await page.request.get('/api/v1/demo/configuration')
  ).json();
  await page.goto('/login');
  await page
    .getByRole('button', {
      name: configuration.enabled ? '체험 시작하기' : 'Demo 로그인',
      exact: true,
    })
    .click();
  await expect(page.locator('.profile-card')).toBeVisible();
  return configuration;
}

function modelRequests(page: Page) {
  const requests: string[] = [];
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      /approval-draft-assistant|work-assistant|leave-assistant|policies\/search|\/ai-review/.test(
        request.url(),
      )
    )
      requests.push(request.url());
  });
  return requests;
}

test('prototype hands confirmed inputs to an unsaved form, then saves through the real API', async ({
  page,
}) => {
  const configuration = await enter(page);
  const models = modelRequests(page);
  let writes = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/approvals'))
      writes++;
  });
  await page.getByRole('link', { name: '업무 체험 안내', exact: true }).click();
  await expect(
    page.getByText('예시 체험 · 실제 AI 호출 없음', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: '빠진 정보 확인', exact: true })
    .click();
  await expect(page.getByLabel('실제 지출일', { exact: true })).toBeFocused();
  await page.getByLabel('실제 지출일', { exact: true }).fill('2026-01-09');
  await page.getByLabel('사용처', { exact: true }).fill('합성 교통 서비스');
  await page
    .getByLabel('증빙 참조 (선택)', { exact: true })
    .fill('PROTO-RECEIPT-001');
  await page
    .getByRole('button', { name: '미리보기 확인', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: '작성할 경비 내용', exact: true }),
  ).toBeFocused();
  await expect(
    page.getByText('아직 저장되지 않았습니다.', { exact: false }),
  ).toBeVisible();
  await page.getByRole('button', { name: '입력 수정', exact: true }).click();
  await expect(page.getByLabel('사용처', { exact: true })).toHaveValue(
    '합성 교통 서비스',
  );
  await page
    .getByLabel('사용처', { exact: true })
    .fill('수정한 합성 교통 서비스');
  await page
    .getByRole('button', { name: '미리보기 확인', exact: true })
    .click();
  await page
    .getByRole('button', { name: '이 내용으로 결재 작성', exact: true })
    .click();
  await expect(page).toHaveURL(/\/approvals\/new\?handoff=manual$/);
  await expect(
    page.getByRole('textbox', { name: '제목', exact: true }),
  ).toHaveValue('CES 출장 교통비 정산');
  await expect(page.getByLabel('사용처', { exact: true })).toHaveValue(
    '수정한 합성 교통 서비스',
  );
  await expect(page.getByLabel('실제 지출일', { exact: true })).toHaveValue(
    '2026-01-09',
  );
  await expect(
    page.getByLabel('실제 지출 금액 (원)', { exact: true }),
  ).toHaveValue('170000');
  await expect(
    page.getByLabel('증빙 참조 (선택)', { exact: true }),
  ).toHaveValue('PROTO-RECEIPT-001');
  expect(writes).toBe(0);
  expect(models).toEqual([]);
  expect(page.url()).not.toContain('RECEIPT');
  await page.getByRole('button', { name: '초안 저장', exact: true }).click();
  await expect(page).toHaveURL(/\/approvals\/[^/]+(?:\?.*)?$/);
  await expect(
    page.getByRole('heading', { name: 'CES 출장 교통비 정산', exact: true }),
  ).toBeVisible();
  expect(writes).toBe(1);
  if (configuration.enabled) {
    const path = '/api/v1' + new URL(page.url()).pathname;
    await page.getByRole('button', { name: '제출', exact: true }).click();
    await page
      .getByRole('dialog', { name: '결재 제출 확인' })
      .getByRole('button', { name: '확인하고 제출', exact: true })
      .click();
    await expect(page.locator('.detail-title-row .status-badge')).toHaveText(
      '결재 대기',
    );
    await page
      .getByRole('region', { name: '체험 다음 단계' })
      .getByRole('button', { name: '결재자로 전환해 계속하기' })
      .click();
    await page.getByRole('tab', { name: '내가 결재할 문서' }).click();
    await expect(
      page.getByRole('link').filter({ hasText: 'CES 출장 교통비 정산' }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole('link')
      .filter({ hasText: 'CES 출장 교통비 정산' })
      .click();
    await page
      .getByLabel('결재 의견')
      .fill('합성 체험의 경비 항목과 증빙 참조를 확인했습니다.');
    await page.getByRole('button', { name: '승인', exact: true }).click();
    await page
      .getByRole('dialog', { name: '결재 승인 확인' })
      .getByRole('button', { name: '확인하고 승인', exact: true })
      .click();
    await expect(page.locator('.detail-title-row .status-badge')).toHaveText(
      '승인',
    );
    await page
      .getByRole('button', { name: '작성자로 돌아가기', exact: true })
      .click();
    expect((await (await page.request.get(path)).json()).status).toBe(
      'APPROVED',
    );
  }
  expect(models).toEqual([]);
});

test('policy library reads actual versioned sections and recovers from a failed request', async ({
  page,
}) => {
  await enter(page);
  const models = modelRequests(page);
  await page.route('**/api/v1/policies', (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: '합성 정책 조회 장애' } },
    }),
  );
  await page.getByRole('link', { name: '회사 규정', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: '합성 정책 조회 장애' }),
  ).toBeVisible();
  await page.unroute('**/api/v1/policies');
  await page
    .getByRole('button', { name: '규정 다시 불러오기', exact: true })
    .click();
  await expect(page.locator('article')).toHaveCount(3);
  const policies = await (await page.request.get('/api/v1/policies')).json();
  for (const policy of policies)
    await expect(
      page.getByRole('heading', { name: policy.title, exact: true }),
    ).toBeVisible();
  await page.getByLabel('업무 분류', { exact: true }).selectOption('EXPENSE');
  await expect(page.locator('article')).toHaveCount(1);
  await page.getByLabel('규정 검색', { exact: true }).fill('영수증');
  await expect(page.locator('details')).toHaveCount(1);
  await expect(page.locator('details')).toContainText('EXPENSE-2');
  await page.getByLabel('규정 검색', { exact: true }).fill('EXPENSE-2');
  await expect(page.locator('details')).toHaveCount(1);
  await expect(page.locator('details')).toHaveAttribute('open', '');
  await expect(page.locator('details')).toContainText('EXPENSE-2');
  await page
    .getByLabel('규정 검색', { exact: true })
    .fill('존재하지않는합성검색어');
  await expect(
    page.getByRole('heading', { name: '일치하는 규정이 없습니다' }),
  ).toBeVisible();
  await page.getByRole('button', { name: '검색 초기화', exact: true }).click();
  await expect(page.locator('article')).toHaveCount(3);
  expect(models).toEqual([]);
});

test('organization and prototype pages stay within the viewport and expose permitted real data', async ({
  page,
}, testInfo) => {
  await enter(page);
  const employee = await (
    await page.request.get('/api/v1/employees/me')
  ).json();
  const departments = await (
    await page.request.get('/api/v1/departments')
  ).json();
  await page.getByRole('link', { name: '내 조직', exact: true }).click();
  const profile = page.getByRole('region', {
    name: '내 업무 관계',
    exact: true,
  });
  await expect(
    profile.getByRole('heading', { name: employee.name, exact: true }),
  ).toBeVisible();
  if (employee.manager)
    await expect(
      profile.getByRole('heading', {
        name: employee.manager.name,
        exact: true,
      }),
    ).toBeVisible();
  await expect(
    page
      .getByRole('region', { name: '조회 가능한 부서', exact: true })
      .getByRole('listitem'),
  ).toHaveCount(departments.length);
  for (const path of ['/organization', '/policies', '/explore']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('.profile-card')).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    expect(results.violations).toEqual([]);
    if (path === '/explore')
      await page.screenshot({
        path: `artifacts/prototype/${testInfo.project.name}-explore.png`,
        fullPage: true,
        style: 'nextjs-portal { display: none; }',
      });
  }
});

test('failed browser storage keeps the preview and invalid stored presets are rejected', async ({
  page,
}) => {
  await enter(page);
  const employee = await (
    await page.request.get('/api/v1/employees/me')
  ).json();
  await page.goto('/explore');
  await page
    .getByRole('button', { name: '빠진 정보 확인', exact: true })
    .click();
  await page.getByLabel('실제 지출일', { exact: true }).fill('2026-01-09');
  await page.getByLabel('사용처', { exact: true }).fill('보존할 합성 사용처');
  await page
    .getByRole('button', { name: '미리보기 확인', exact: true })
    .click();
  await page.evaluate(() => {
    Storage.prototype.setItem = () => {
      throw new Error('synthetic storage unavailable');
    };
  });
  await page
    .getByRole('button', { name: '이 내용으로 결재 작성', exact: true })
    .click();
  await expect(
    page
      .getByRole('alert')
      .filter({ hasText: '입력 내용을 옮기지 못했습니다' }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/explore$/);
  await expect(
    page.getByText('보존할 합성 사용처', { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.evaluate(
    (id) =>
      sessionStorage.setItem(
        `jhworks:manual-draft:${id}`,
        JSON.stringify({
          content: '잘못된 미리보기',
          type: 'EXPENSE',
          expiresAt: Date.now() + 60000,
          expensePreset: { title: '불완전', amount: -1, details: null },
        }),
      ),
    employee.id,
  );
  await page.goto('/approvals/new?handoff=manual');
  await expect(
    page.getByRole('textbox', { name: '업무 내용', exact: true }),
  ).toBeEmpty();
  await expect(page.getByRole('status')).toContainText(
    '이어받을 입력이 없거나',
  );
});
