import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  testMatch: '**/public-demo.spec.ts',
  testIgnore: [],
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-public-demo-report' }]],
  webServer: [
    {
      command: 'cd apps/api && uv run uvicorn tests.e2e_server:app --port 8100',
      url: 'http://localhost:8100/api/v1/health', reuseExistingServer: false,
      env: { JHWORKS_PUBLIC_DEMO_ENABLED: 'true', JHWORKS_AI_ENABLED: 'false' },
    },
    {
      command: 'pnpm --filter @jhworks/web exec next dev --port 3100',
      url: 'http://localhost:3100/login', reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: '/api/v1', API_PROXY_TARGET: 'http://127.0.0.1:8100' },
    },
  ],
});
