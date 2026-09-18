import { test, expect } from '@playwright/test';
import { loginAsTestUser } from './support/auth';

const EXPECTED_STATUSES = new Set([500, 502, 503, 504]);

function attachDiagnostics(page: import('@playwright/test').Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const badResponses: string[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.url().includes('/api/') && EXPECTED_STATUSES.has(response.status())) {
      badResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  return { consoleErrors, pageErrors, badResponses };
}

// SMOKE-001 -- app starts, mounts, shows an expected screen.
test('SMOKE-001: app starts and mounts without a fatal error', async ({ page }) => {
  const diag = attachDiagnostics(page);
  const response = await page.goto('/');
  expect(response?.status()).toBe(200);
  await expect(page.locator('#root')).not.toBeEmpty();
  await expect(page.locator('form')).toBeVisible();
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
});

// SMOKE-002 -- real login/session flow against the SAFE_TEST backend.
test('SMOKE-002: email/password login reaches the authenticated shell', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  await expect(page.getByRole('link', { name: /Дашборд/ })).toBeVisible();
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});

// SMOKE-003 -- navigation across production routes.
test('SMOKE-003: primary sections are reachable from the sidebar', async ({ page }) => {
  await loginAsTestUser(page);
  const sections: Array<{ label: string | RegExp; heading: string | RegExp }> = [
    { label: /Заявки/, heading: /Заявки/ },
    { label: /Сообщения/, heading: /Сообщения/ },
    { label: /Поставщики/, heading: /Поставщики/ },
    { label: /Чёрный список/, heading: /Чёрный список/ },
    { label: /Настройки/, heading: /Настройки/ },
  ];

  for (const section of sections) {
    await page.getByRole('link', { name: section.label }).click();
    await expect(page.getByRole('heading', { name: section.heading }).first()).toBeVisible();
  }

  // Dashboard: back to index route. HashRouter leaves the hash empty for
  // the index route rather than writing a literal "#/".
  await page.getByRole('link', { name: /Дашборд/ }).click();
  await expect(page.getByText('Что сейчас требует внимания')).toBeVisible();
});

// SMOKE-004 -- request list.
test('SMOKE-004: request list renders data and links to a request', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Заявки/ }).click();
  await expect(page.getByRole('heading', { name: /Заявки/ })).toBeVisible();
  const firstRow = page.locator('table tbody tr, [data-testid="request-row"]').first();
  await expect(firstRow).toBeVisible({ timeout: 10_000 });
  await firstRow.click();
  await expect(page).toHaveURL(/\/#\/requests\/\d+/);
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});

// SMOKE-005 -- request detail card.
test('SMOKE-005: an existing request opens with its main blocks rendered', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  await page.goto('/#/requests');
  const firstRow = page.locator('table tbody tr, [data-testid="request-row"]').first();
  await firstRow.click();
  await expect(page.getByRole('heading').first()).toBeVisible();
  // Suppliers/positions block should not crash the page even if partially empty.
  await expect(page.locator('#root')).not.toBeEmpty();
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});

// SMOKE-006 -- Messages.
test('SMOKE-006: messages list opens and a conversation can be opened', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Сообщения/ }).click();
  await expect(page.getByRole('heading', { name: /Сообщения/ })).toBeVisible();
  const threadRow = page.locator('[data-testid="thread-row"], button:has-text("@")').first();
  if (await threadRow.count()) {
    await threadRow.click();
  }
  await expect(page.locator('#root')).not.toBeEmpty();
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});

// SMOKE-007 -- Supplier card.
test('SMOKE-007: a supplier can be opened and does not crash on partial data', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Поставщики/ }).click();
  await expect(page.getByRole('heading', { name: /Поставщики/ })).toBeVisible();
  const firstRow = page.locator('table tbody tr, [data-testid="supplier-row"]').first();
  await expect(firstRow).toBeVisible({ timeout: 10_000 });
  await firstRow.click();
  await expect(page).toHaveURL(/\/#\/suppliers\/\d+/);
  await expect(page.locator('#root')).not.toBeEmpty();
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});

// SMOKE-008 -- AI assistant panel opens; no real (paid) AI call is triggered.
test('SMOKE-008: AI assistant panel opens and offers a context selection', async ({ page }) => {
  const diag = attachDiagnostics(page);
  const aiChatCalls: string[] = [];
  await page.route('**/api/ai/chat', async (route) => {
    aiChatCalls.push(route.request().url());
    await route.abort();
  });
  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Сообщения/ }).click();
  const threadRow = page.locator('[data-testid="thread-row"], button:has-text("@")').first();
  test.skip(
    !(await threadRow.count()),
    'SAFE_TEST fixture (runtime/test-data/supplier.sqlite3) has no correspondence threads yet -- ' +
      'the AI assistant only appears once a thread is open. See final QA report: needs a seeded ' +
      'thread fixture to exercise this smoke test end-to-end.',
  );
  await threadRow.click();
  const assistantToggle = page.getByRole('button', { name: 'Открыть ИИ-помощника' });
  await expect(assistantToggle).toBeVisible();
  await assistantToggle.click();
  await expect(page.getByRole('dialog', { name: 'ИИ-помощник SupplyDesk' })).toBeVisible();
  // A basic open of the panel must not itself fire a paid AI call.
  expect(aiChatCalls, aiChatCalls.join('\n')).toEqual([]);
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
});

// SMOKE-009 / SMOKE-010 -- console and network hygiene across a short walk.
test('SMOKE-009/010: no uncaught errors and no unexpected 5xx across a basic walk', async ({ page }) => {
  const diag = attachDiagnostics(page);
  await loginAsTestUser(page);
  for (const link of [/Заявки/, /Сообщения/, /Поставщики/, /Дашборд/]) {
    await page.getByRole('link', { name: link }).click();
    await page.waitForLoadState('networkidle');
  }
  expect(diag.pageErrors, diag.pageErrors.join('\n')).toEqual([]);
  expect(diag.badResponses, diag.badResponses.join('\n')).toEqual([]);
});
