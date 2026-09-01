import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: /real-email-diagnostic\.spec\.ts/,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: process.env.AUDIT_BASE_URL ?? 'http://127.0.0.1:8010',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'real-email', use: { viewport: { width: 1640, height: 900 } } }],
});
