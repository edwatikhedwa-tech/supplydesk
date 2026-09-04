import { defineConfig } from '@playwright/test';
import type { EyesFixture } from '@applitools/eyes-playwright/fixture';

const viewports = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'laptop-1280', width: 1280, height: 720 },
  { name: 'mobile-390', width: 390, height: 844 },
].map(({ name, width, height }) => ({
  name,
  use: { viewport: { width, height } },
}));

export default defineConfig<EyesFixture>({
  testDir: './tests/visual',
  testMatch: '**/messages.visual.spec.ts',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.AUDIT_BASE_URL ?? 'http://127.0.0.1:18000',
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    eyesConfig: {
      appName: 'SupplyDesk',
      batch: { name: process.env.APPLITOOLS_BATCH_NAME ?? 'SupplyDesk /messages Eyes pilot' },
      type: 'classic',
      failTestsOnDiff: 'afterEach',
    },
  },
  projects: viewports,
});
