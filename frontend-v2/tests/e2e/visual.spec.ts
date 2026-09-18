import { test, expect } from '@playwright/test';
import { loginAsTestUser } from './support/auth';

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

const screens: Array<{ name: string; goto: (page: import('@playwright/test').Page) => Promise<void> }> = [
  {
    name: 'dashboard',
    goto: async (page) => {
      await loginAsTestUser(page);
    },
  },
  {
    name: 'requests',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Заявки/ }).click();
    },
  },
  {
    name: 'request-detail',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.goto('/#/requests');
      await page.locator('table tbody tr, [data-testid="request-row"]').first().click();
    },
  },
  {
    name: 'messages',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Сообщения/ }).click();
    },
  },
  {
    name: 'suppliers',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Поставщики/ }).click();
    },
  },
];

for (const { name, goto } of screens) {
  test(`visual: ${name} desktop baseline has no overflow`, async ({ page }) => {
    await goto(page);
    await page.waitForLoadState('networkidle');
    await page.addStyleTag({
      content: '*, *::before, *::after { animation: none !important; transition: none !important; }',
    });
    await expectNoHorizontalOverflow(page);
    await expect(page).toHaveScreenshot(`${name}-desktop-1440.png`, { fullPage: true, maxDiffPixelRatio: 0.02 });
  });
}
