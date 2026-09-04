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

test('SAFE_TEST runtime displays its environment badge on the app shell', async ({ page }) => {
  const login = await page.request.post('/api/auth/login', {
    data: { email: 'test.user@example.invalid', password: 'TestOnly-Synthetic-20260901' },
  });
  expect(login.status()).toBe(200);

  await page.goto('/messages', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-runtime-badge]')).toHaveText('SAFE TEST · DISPOSABLE DATA · PORT 18000');
});
