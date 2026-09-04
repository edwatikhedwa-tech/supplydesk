import { expect, test } from '@applitools/eyes-playwright/fixture';
import type { Eyes } from '@applitools/eyes-playwright/fixture';
import type { Page, TestInfo } from '@playwright/test';

type CorrespondenceItem = {
  request_id: number;
  supplier_id: number;
  last_message_direction?: string | null;
};

const eyesKeyConfigured = Object.prototype.hasOwnProperty.call(process.env, 'APPLITOOLS_API_KEY');
const SAFE_TEST_EMAIL = 'test.user@example.invalid';
const SAFE_TEST_PASSWORD = 'TestOnly-Synthetic-20260901';

async function login(page: Page) {
  const response = await page.request.post('/api/auth/login', {
    data: { email: SAFE_TEST_EMAIL, password: SAFE_TEST_PASSWORD },
  });
  expect(response.status()).toBe(200);
  const me = await page.request.get('/api/auth/me');
  expect(me.status()).toBe(200);
  expect((await me.json()).authenticated).toBe(true);
}

async function loadRealConversation(page: Page): Promise<CorrespondenceItem> {
  const response = await page.request.get('/api/correspondence');
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as { items?: CorrespondenceItem[] };
  const thread = payload.items?.find((item) => Number.isInteger(item.request_id) && Number.isInteger(item.supplier_id));
  if (!thread) {
    throw new Error('BLOCKED: SAFE_TEST has no synthetic correspondence. Seed a disposable conversation before running the Eyes pilot.');
  }
  return thread;
}

async function captureLocalAndEyes(page: Page, name: string, eyes: Eyes, testInfo: TestInfo) {
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-${name}.png`), fullPage: false });
  await eyes.check(`Messages / ${name}`, { matchLevel: 'Dynamic' });
}

test.describe('SupplyDesk /messages Applitools Eyes pilot', () => {
  test.skip(!eyesKeyConfigured, 'BLOCKED: APPLITOOLS_API_KEY is not configured; no Eyes request is attempted.');

  test('checks request list, real conversation and reply composer', async ({ page, eyes }, testInfo) => {
    await login(page);

    await page.goto('/messages', { waitUntil: 'networkidle' });
    await page.addStyleTag({ content: '*, *::before { animation: none !important; transition: none !important; }' });
    await expect(page.getByRole('heading', { name: 'Мои заявки' })).toBeVisible();
    const thread = await loadRealConversation(page);
    await captureLocalAndEyes(page, 'request-list', eyes, testInfo);

    await page.goto(`/messages?thread=${thread.request_id}:${thread.supplier_id}`, { waitUntil: 'networkidle' });
    await page.addStyleTag({ content: '*, *::before { animation: none !important; transition: none !important; }' });
    await expect(page.getByText('Переписка', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ответить', exact: true })).toBeVisible();
    await captureLocalAndEyes(page, 'conversation', eyes, testInfo);

    await page.getByRole('button', { name: 'Ответить', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Ответить' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('textbox', { name: 'Текст письма' })).toBeFocused();
    await captureLocalAndEyes(page, 'reply-composer', eyes, testInfo);
    await dialog.getByRole('button', { name: 'Закрыть форму ответа' }).click();
    await expect(dialog).toBeHidden();
  });
});
