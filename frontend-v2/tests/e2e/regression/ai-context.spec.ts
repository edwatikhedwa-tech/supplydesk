import { test, expect } from '@playwright/test';
import { loginAsTestUser } from '../support/auth';
import { loadQaFixture } from '../support/fixture';

/**
 * Regression guard for the historical "AI receives all suppliers of a
 * request" context-leak bug (fixed server-side in commit 0d16945; see
 * docs/product/AI_ASSISTANT.md and tests/test_ai_context_scoping.py for the
 * authoritative backend re-validation via AiChatService/
 * MailRepository.get_thread_owned -- that test is what actually proves the
 * server-side security boundary, at a larger scale (132 suppliers) than is
 * practical here).
 *
 * This frontend test checks the client's own contract on top of that
 * boundary: for the fixture Request -> Supplier A (has correspondence),
 * Supplier B (no correspondence), Supplier C (has correspondence)
 * (scripts/seed_qa_fixtures.py, seeded by playwright.config.ts's
 * globalSetup), opening the AI assistant and selecting "all suppliers"
 * must produce a thread_ids payload containing exactly A's and C's thread
 * ids -- never a fabricated id for B, which has no thread at all because it
 * never had any correspondence.
 */
test('AI chat request payload includes only suppliers with real correspondence (A, C), never B', async ({ page }) => {
  await loginAsTestUser(page);
  const fixture = await loadQaFixture(page.request);
  const expectedThreadIds = [fixture.threadAId, fixture.threadCId].sort((a, b) => a - b);

  let capturedBody: { thread_ids?: number[]; suppliers?: unknown[] } | null = null;
  await page.route('**/api/ai/chat', async (route) => {
    capturedBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', reply: 'ok', spent_rub: 0, limit_rub: 100, message: 'ok', conversation_id: 1 }),
    });
  });

  // Deep-link straight to thread A instead of clicking through the grouped,
  // auto-refreshing thread list (flaky: the list's expand/collapse state
  // can reset mid-click when a background refetch lands).
  await page.goto(`/#/messages?request=${fixture.requestId}&supplier=${fixture.supplierAId}`);
  await expect(page.getByText('ООО КЕЙС А', { exact: false }).first()).toBeVisible({ timeout: 10_000 });

  await page.getByRole('button', { name: 'Открыть ИИ-помощника' }).click();
  const dialog = page.getByRole('dialog', { name: 'ИИ-помощник SupplyDesk' });
  await expect(dialog).toBeVisible();

  const selectAllSiblings = dialog.getByRole('button', { name: 'Выбрать остальных поставщиков' });
  await expect(selectAllSiblings).toBeVisible();
  await selectAllSiblings.click();

  const composer = dialog.getByPlaceholder('Например: сравни цену, сроки и риски');
  await composer.fill('Проверка контекста');
  await dialog.getByRole('button', { name: 'Отправить' }).click();

  await expect.poll(() => capturedBody).not.toBeNull();
  const body = capturedBody as unknown as { thread_ids: number[]; suppliers?: unknown[] };
  expect(Array.isArray(body.thread_ids), JSON.stringify(body)).toBe(true);
  expect(body.suppliers, JSON.stringify(body)).toBeUndefined();
  expect([...body.thread_ids].sort((a, b) => a - b)).toEqual(expectedThreadIds);
});
