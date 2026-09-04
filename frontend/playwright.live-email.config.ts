import { defineConfig } from '@playwright/test';
import { assertRuntime } from './runtimeGuard';

const runtime = assertRuntime({
  surface: 'browser',
  baseUrl: process.env.AUDIT_BASE_URL,
  backendUrl: process.env.RUNTIME_BACKEND_URL,
});

export default defineConfig({
  testDir: './tests',
  testMatch: '**/live-email-regression.spec.ts',
  timeout: 180_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: runtime.baseUrl,
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
  },
});
