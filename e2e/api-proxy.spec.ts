import { expect, test } from '@playwright/test';

test('same-origin API proxy preserves cookie, CSRF, and request ID boundaries', async ({ request }) => {
  const denied = await request.post('/api/v1/auth/login', {
    headers: { Origin: 'https://untrusted.example', 'X-Request-ID': 'proxy-csrf-test' },
    data: { email: 'seojin.yoon@jhworks.test', password: 'demo1234' },
  });
  expect(denied.status()).toBe(403);
  expect(denied.headers()['x-request-id']).toBe('proxy-csrf-test');
  expect(denied.headers()['set-cookie']).toBeUndefined();

  const loggedIn = await request.post('/api/v1/auth/login', {
    headers: { Origin: 'http://localhost:3100' },
    data: { email: 'seojin.yoon@jhworks.test', password: 'demo1234' },
  });
  expect(loggedIn.ok()).toBe(true);
  expect(loggedIn.headers()['set-cookie']).toContain('HttpOnly');
  const me = await request.get('/api/v1/employees/me', {
    headers: { 'X-Request-ID': 'proxy-authenticated-test' },
  });
  expect(me.status()).toBe(200);
  expect((await me.json()).id).toBe('emp_sales_001');
  expect(me.headers()['x-request-id']).toBe('proxy-authenticated-test');
});
