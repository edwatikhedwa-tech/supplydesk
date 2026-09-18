import type { Page } from '@playwright/test';

/**
 * Synthetic SAFE_TEST credentials, disposable SQLite backend only.
 * Same fixture already used by frontend/tests/fast-browser-smoke.spec.ts.
 * Never valid against production; committing this value is safe.
 */
export const TEST_USER = {
  email: 'test.user@example.invalid',
  password: 'TestOnly-Synthetic-20260901',
};

export async function loginAsTestUser(page: Page): Promise<void> {
  await page.goto('/');
  // NOTE (GAP, not fixed here -- see final QA report): the <label> elements
  // on this form have no htmlFor/id association with their inputs, so
  // getByLabel() cannot find them. Selecting by input[type] within the form
  // instead, since both fields are on the same login form.
  const form = page.locator('form');
  const emailInput = form.locator('input[type="email"]');
  await emailInput.waitFor({ state: 'visible', timeout: 10_000 });
  await emailInput.fill(TEST_USER.email);
  await form.locator('input[type="password"]').fill(TEST_USER.password);
  await form.getByRole('button', { name: 'Войти', exact: true }).click();
  // HashRouter renders the index route with an empty hash (no literal "#/"),
  // so URL-based waiting is unreliable here; wait for the authenticated
  // shell to actually mount instead.
  await page.getByRole('link', { name: /Дашборд/ }).waitFor({ state: 'visible', timeout: 10_000 });
}
