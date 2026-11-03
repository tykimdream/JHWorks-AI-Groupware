import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  testMatch: '**/approval-performance.spec.ts',
  testIgnore: [],
  webServer: [
    {
      command: 'cd apps/api && uv run uvicorn tests.performance_e2e_server:app --port 8100',
      url: 'http://localhost:8100/api/v1/health',
      reuseExistingServer: false,
    },
    {
      command: 'node tools/start-web-preview.mjs',
      url: 'http://localhost:3100/login',
      reuseExistingServer: false,
    },
  ],
});
