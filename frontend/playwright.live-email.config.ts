import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/live-email-regression.spec.ts',
  timeout: 180_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.AUDIT_BASE_URL ?? 'http://127.0.0.1:8000',
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
  },
});
