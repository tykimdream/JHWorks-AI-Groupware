import { expect, test } from '@playwright/test';

test('HTML uses fresh CSP nonces and the rendered login remains interactive', async ({ page, request }) => {
  const first = await request.get('/login');
  const second = await request.get('/login');
  const csp = first.headers()['content-security-policy'];
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");
  expect(first.headers()['cache-control']).toMatch(
    process.env.E2E_PRODUCTION === '1' ? /no-store/ : /no-cache|no-store/,
  );
  const nonce = csp.match(/'nonce-([^']+)'/)?.[1];
  expect(nonce).toBeTruthy();
  expect(second.headers()['content-security-policy']).not.toContain(`'nonce-${nonce}'`);
  expect(await first.text()).toContain(`nonce="${nonce}"`);
  if (process.env.E2E_PRODUCTION === '1') {
    expect(csp).not.toContain("'unsafe-eval'");
    expect(csp.split(';').find((part) => part.trim().startsWith('script-src'))).not.toContain("'unsafe-inline'");
  }
  const violations: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && /content.security.policy|violates.*directive|refused to execute/i.test(message.text())) {
      violations.push(message.text());
    }
  });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo 로그인', exact: true }).click();
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { name: '어떤 업무를 도와드릴까요?' })).toBeVisible();
  expect(violations).toEqual([]);
});
