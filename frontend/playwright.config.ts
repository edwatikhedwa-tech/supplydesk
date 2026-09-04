import { defineConfig } from '@playwright/test';
import { assertRuntime } from './runtimeGuard';

const runtime = assertRuntime({
  surface: 'browser',
  baseUrl: process.env.AUDIT_BASE_URL,
  backendUrl: process.env.RUNTIME_BACKEND_URL,
});

const viewports = [
  { name: 'desktop-max', width: 1920, height: 1080 },
  { name: 'desktop-user', width: 1640, height: 900 },
  { name: 'desktop-wide', width: 1440, height: 900 },
  { name: 'desktop-compact', width: 1280, height: 800 },
  { name: 'tablet-landscape', width: 1024, height: 768 },
  { name: 'tablet-portrait', width: 768, height: 1024 },
  { name: 'mobile-large', width: 390, height: 844 },
  { name: 'mobile-small', width: 360, height: 800 },
].map(({ name, width, height }) => ({ name, use: { viewport: { width, height } } }));

export default defineConfig({
  testDir: './tests',
  testMatch: /(?:frontend-audit|fast-browser-smoke|campaign-ui|mailru-ui)\.spec\.ts/,
  timeout: 60_000,
  expect: {
    timeout: 5_000,
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },
  fullyParallel: false,
  // Three.js on the login screen is GPU/CPU-heavy in headless Chromium.
  // Eight concurrent viewport projects starved one another and produced false
  // 45-second timeouts; four keeps the matrix parallel without oversubscription.
  workers: 4,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'artifacts/playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: runtime.baseUrl,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: viewports,
});
