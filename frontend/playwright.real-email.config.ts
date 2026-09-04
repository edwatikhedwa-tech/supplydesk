import { defineConfig } from '@playwright/test';
import { assertRuntime } from './runtimeGuard';

const runtime = assertRuntime({
  surface: 'browser',
  baseUrl: process.env.AUDIT_BASE_URL,
  backendUrl: process.env.RUNTIME_BACKEND_URL,
});

export default defineConfig({
  testDir: './tests',
  testMatch: /real-email-diagnostic\.spec\.ts/,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: runtime.baseUrl,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'real-email', use: { viewport: { width: 1640, height: 900 } } }],
});
