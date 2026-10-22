import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/public-demo.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:3100',
    trace: 'retain-on-failure',
    launchOptions: process.env.E2E_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.E2E_CHROMIUM_EXECUTABLE } : {},
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'], deviceScaleFactor: 1, defaultBrowserType: 'chromium' } },
  ],
  webServer: [
    {
      command: 'cd apps/api && uv run uvicorn tests.e2e_server:app --port 8100',
      url: 'http://localhost:8100/api/v1/health',
      reuseExistingServer: false,
    },
    {
      command: 'pnpm --filter @jhworks/web exec next dev --port 3100',
      url: 'http://localhost:3100/login',
      env: { NEXT_PUBLIC_API_URL: '/api/v1', API_PROXY_TARGET: 'http://127.0.0.1:8100' },
      reuseExistingServer: false,
    },
  ],
});
