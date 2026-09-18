import { test, expect } from '@playwright/test';
import { loginAsTestUser } from '../support/auth';

/**
 * Regression guard for the historical "AI receives all suppliers of a
 * request" context-leak bug (fixed server-side in commit 0d16945; see
 * docs/product/AI_ASSISTANT.md and tests/test_ai_context_scoping.py for the
 * authoritative backend re-validation via MailRepository.get_thread_owned).
 *
 * This frontend test only checks the client's own request shape: it must
 * send an explicit, bounded thread_ids selection, never an unrelated bulk
 * list of every supplier/company on the request. The server-side
 * authorization boundary itself is intentionally NOT re-tested here --
 * that belongs to the backend suite referenced above.
 */
test('AI chat request payload sends a bounded thread selection, not a bulk supplier list', async ({ page }) => {
  let capturedBody: Record<string, unknown> | null = null;

  await page.route('**/api/ai/chat', async (route) => {
    capturedBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', reply: 'ok', spent_rub: 0, limit_rub: 100, message: 'ok', conversation_id: 1 }),
    });
  });

  await loginAsTestUser(page);
  await page.getByRole('link', { name: /Сообщения/ }).click();
  const threadRow = page.locator('[data-testid="thread-row"], button:has-text("@")').first();
  test.skip(
    !(await threadRow.count()),
    'SAFE_TEST fixture (runtime/test-data/supplier.sqlite3) has no correspondence threads yet -- ' +
      'the AI assistant only appears once a thread is open. See final QA report: this regression ' +
      'guard needs a seeded thread fixture to actually run.',
  );
  await threadRow.click();

  await page.getByRole('button', { name: 'Открыть ИИ-помощника' }).click();
  const composer = page.getByPlaceholder('Например: сравни цену, сроки и риски');
  await composer.fill('Проверка контекста');
  await page.getByRole('button', { name: 'Отправить' }).click();
  await expect.poll(() => capturedBody).not.toBeNull();

  const body = capturedBody as unknown as { thread_ids?: unknown[]; suppliers?: unknown[] };
  expect(Array.isArray(body.thread_ids), JSON.stringify(body)).toBe(true);
  expect(body.suppliers, JSON.stringify(body)).toBeUndefined();
});
