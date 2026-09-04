import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const routes = [
  { path: '/experiment/ui-shadcn-v2', heading: 'День под контролем', slug: 'dashboard' },
  { path: '/experiment/ui-shadcn-v2/requests', heading: 'Мои заявки', slug: 'requests' },
  { path: '/experiment/ui-shadcn-v2/suppliers', heading: 'Поставщики', slug: 'suppliers' },
  { path: '/experiment/ui-shadcn-v2/messages', heading: 'Переписка', slug: 'messages' },
];

async function expectNoOverflow(page: Page) {
  const geometry = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const visible = (element: Element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    };
    const outside = [...document.body.querySelectorAll('*')]
      .filter(visible)
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter(({ rect }) => rect.left < -1 || rect.right > viewportWidth + 1)
      .slice(0, 10)
      .map(({ element, rect }) => ({ tag: element.tagName.toLowerCase(), className: typeof element.className === 'string' ? element.className.slice(0, 100) : '', left: Math.round(rect.left), right: Math.round(rect.right) }));
    return { viewportWidth, scrollWidth: document.documentElement.scrollWidth, outside };
  });
  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.viewportWidth + 1);
  expect(geometry.outside, JSON.stringify(geometry)).toEqual([]);
}

test.describe('SupplyDesk UI Experiment v2', () => {
  test.use({ reducedMotion: 'reduce' });

  test('renders the four representative screens with stable geometry and a11y', async ({ page }, testInfo) => {
    await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
    for (const route of routes) {
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('heading', { name: route.heading, exact: true })).toBeVisible();
      await expectNoOverflow(page);
      const artifact = `artifacts/ui-shadcn-v2-20260904/${testInfo.project.name}-${route.slug}.png`;
      await page.screenshot({ path: artifact, fullPage: false });
      const axeResults = await new AxeBuilder({ page }).analyze();
      expect(axeResults.violations, `${route.path}\n${axeResults.violations.map((item) => item.id).join(', ')}`).toEqual([]);
    }
  });

  test('keeps the core presentation states interactive without production writes', async ({ page }) => {
    await page.goto('/experiment/ui-shadcn-v2/requests', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Требуют внимания' }).click();
    await expect(page.getByRole('button', { name: 'Запасные части для компрессоров' })).toBeVisible();
    await page.getByRole('button', { name: 'Запасные части для компрессоров' }).click();
    await expect(page.getByRole('dialog', { name: 'Запасные части для компрессоров' })).toBeVisible();
    await page.getByRole('button', { name: 'Закрыть предпросмотр' }).click();

    await page.goto('/experiment/ui-shadcn-v2/suppliers', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Поиск по поставщикам').fill('ОЛЛБРИК');
    await expect(page.getByRole('button', { name: 'ООО «ОЛЛБРИК»' })).toBeVisible();
    await page.getByRole('checkbox', { name: 'Выбрать ООО «ОЛЛБРИК»' }).check();
    await expect(page.getByText('поставщика выбрано')).toBeVisible();

    await page.goto('/experiment/ui-shadcn-v2/messages', { waitUntil: 'domcontentloaded' });
    await page.getByRole('tab', { name: 'Без привязки' }).click();
    await expect(page.getByRole('tab', { name: 'Без привязки' })).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('tab', { name: 'По заявкам' }).click();
    await page.getByRole('button', { name: /Ответить поставщику/ }).click();
    await expect(page.getByRole('status')).toContainText('presentation-only');
    await expectNoOverflow(page);
  });

  test('mobile navigation exposes the four routes', async ({ page }, testInfo) => {
    test.skip(!testInfo.project.name.startsWith('mobile-'), 'This interaction is specific to the mobile navigation strategy.');
    await page.goto('/experiment/ui-shadcn-v2', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Открыть навигацию' }).click();
    await expect(page.getByRole('navigation', { name: 'Навигация эксперимента' })).toBeVisible();
    await page.locator('.sd-v2-mobile-drawer').getByRole('link', { name: 'Заявки', exact: true }).click();
    await expect(page).toHaveURL(/\/experiment\/ui-shadcn-v2\/requests$/);
    await expect(page.getByRole('heading', { name: 'Мои заявки', exact: true })).toBeVisible();
    await expectNoOverflow(page);
  });
});
