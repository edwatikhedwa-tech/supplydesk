import { test, expect } from '@playwright/test';
import { loginAsTestUser } from './support/auth';

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

test('mobile: navigation collapses without horizontal overflow', async ({ page }) => {
  await loginAsTestUser(page);
  await page.waitForLoadState('networkidle');
  await expectNoHorizontalOverflow(page);
  await expect(page).toHaveScreenshot('mobile-nav-390.png', { fullPage: true, maxDiffPixelRatio: 0.02 });
});

test('mobile: messages stay usable at 390px', async ({ page }) => {
  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Сообщения/ }).click();
  await page.waitForLoadState('networkidle');
  await expectNoHorizontalOverflow(page);
  // Higher tolerance than the other baselines: this screen renders live
  // relative timestamps ("N минут назад") that shift a few pixels of text
  // between runs without being a layout regression.
  await expect(page).toHaveScreenshot('mobile-messages-390.png', { fullPage: true, maxDiffPixelRatio: 0.04 });
});

// Known FAIL, left failing intentionally (see final QA report):
//   Expected: the first request row is visible and clickable at 390px width.
//   Actual:   the row exists in the DOM but Playwright reports it as not
//             visible/stable, and the click never lands within the test
//             timeout -- the Requests table has no mobile/card layout, so
//             at 390px its row content is effectively unusable even though
//             expectNoHorizontalOverflow() does not catch it (no scrollbar,
//             just an unusable row).
//   Requirement: docs/ui-design-system.md's "постепенное раскрытие" /
//             mobile principles imply core lists must stay usable at phone
//             widths.
//   Severity: P2 (Requests list is usable at tablet/desktop; only the
//             390px phone breakpoint is affected).
test('mobile: request detail stays usable at 390px', async ({ page }) => {
  await loginAsTestUser(page);
  await page.goto('/#/requests');
  await page.locator('table tbody tr, [data-testid="request-row"]').first().click();
  await page.waitForLoadState('networkidle');
  await expectNoHorizontalOverflow(page);
  await expect(page).toHaveScreenshot('mobile-request-detail-390.png', { fullPage: true, maxDiffPixelRatio: 0.02 });
});
