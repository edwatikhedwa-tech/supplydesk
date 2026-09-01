import { test, expect } from '@playwright/test';

test('real login route starts and accepts a provider interaction', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const response = await page.goto('/login', { waitUntil: 'domcontentloaded' });

  expect(response?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Вход в рабочее пространство' })).toBeVisible();

  const mailruButton = page.getByRole('button', { name: 'Войти через Mail.ru' });
  await expect(mailruButton).toBeVisible();
  await mailruButton.click();
  await expect(page.getByRole('alert')).toContainText('Вход через Mail.ru пока не подключён.');

  expect(pageErrors).toEqual([]);
});
