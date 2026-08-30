import { test, expect } from '@playwright/test';

const stories = [
  'mail-emailrenderer--plain-text',
  'mail-emailrenderer--rich-html',
  'mail-emailrenderer--remote-images-blocked',
  'mail-emailrenderer--marketing-spacer-cleanup',
];

for (const storyId of stories) {
  test(`${storyId} renders within its viewport`, async ({ page }) => {
    await page.goto(`/iframe.html?id=${storyId}&viewMode=story`, { waitUntil: 'networkidle' });
    await expect(page.locator('#storybook-root')).toBeVisible();
    const component = page.locator('#storybook-root > div').first();
    await expect(component).toBeVisible();
    const emailFrame = page.locator('#storybook-root iframe[title="Содержимое письма"]');
    await expect(emailFrame).toBeVisible();

    const geometry = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyTextLength: document.querySelector('iframe[title="Содержимое письма"]')?.contentDocument?.body?.innerText.length ?? 0,
      emailScrollWidth: document.querySelector('iframe[title="Содержимое письма"]')?.contentDocument?.documentElement.scrollWidth ?? 0,
      emailClientWidth: document.querySelector('iframe[title="Содержимое письма"]')?.contentDocument?.documentElement.clientWidth ?? 0,
    }));
    expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);
    expect(geometry.emailScrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.emailClientWidth + 1);
    expect(geometry.bodyTextLength).toBeGreaterThan(20);
    await expect(component).toHaveScreenshot(`${storyId}.png`);
  });
}
