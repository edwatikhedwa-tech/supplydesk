import { defineConfig } from '@playwright/test';
import { assertRuntime } from './runtimeGuard';

const runtime = assertRuntime({
  surface: 'storybook',
  baseUrl: 'http://127.0.0.1:6006',
});

export default defineConfig({
  testDir: './tests',
  testMatch: /(?:storybook-visual|email-renderer-responsive)\.spec\.ts/,
  timeout: 45_000,
  expect: {
    timeout: 5_000,
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },
  reporter: [['list'], ['html', { outputFolder: 'artifacts/storybook-playwright-report', open: 'never' }]],
  use: {
    baseURL: runtime.baseUrl,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run storybook -- --ci --port 6006',
    url: 'http://127.0.0.1:6006/iframe.html?id=mail-emailrenderer--rich-html&viewMode=story',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
