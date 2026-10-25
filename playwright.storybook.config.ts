import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './storybook-tests', outputDir: 'test-results-storybook', fullyParallel: false, workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-storybook-report' }]],
  use: { baseURL: 'http://127.0.0.1:6006/storybook/', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'], deviceScaleFactor: 1, defaultBrowserType: 'chromium' } },
  ],
  webServer: { command: 'node tools/serve-storybook.mjs', url: 'http://127.0.0.1:6006/storybook/', reuseExistingServer: false },
});
