import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const yandexAccount = {
  id: 55,
  provider: 'yandex',
  email: 'buyer@example.com',
  auth_mode: 'oauth',
  status: 'connected',
  connected: true,
  outgoing_enabled: true,
  incoming_enabled: true,
  incoming_health: 'healthy',
  incoming_last_success_at: '2026-08-30T09:13:41+00:00',
  incoming_last_error: null,
  last_error: null,
  updated_at: '2026-08-29T10:00:00+00:00',
};

const mailruAccount = {
  id: 56,
  provider: 'mailru',
  email: 'buyer@mail.ru',
  auth_mode: 'app_password',
  credential_reference: 'mailru-account:56',
  status: 'connected',
  connected: true,
  outgoing_enabled: true,
  incoming_enabled: true,
  incoming_health: 'healthy',
  incoming_last_success_at: '2026-08-30T09:13:42+00:00',
  incoming_last_error: null,
  last_error: null,
  updated_at: '2026-08-29T10:00:00+00:00',
};

const requestDetail = {
  request: {
    id: 1099,
    name: 'Mail.ru continuation acceptance',
    description: 'Проверка безопасного переключения провайдера.',
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-29T10:00:00+00:00',
    status: 'completed',
    search_progress: 1,
    search_total: 1,
    search_depth: 1,
    last_error: null,
    updated_at: '2026-08-29T10:00:00+00:00',
    positions_count: 0,
    suppliers_count: 0,
    sent_count: 0,
    replies_count: 0,
  },
  positions: [],
  items: [],
};

const campaignSummary = {
  campaign_id: 7001,
  operation_id: 8001,
  request_id: 1099,
  mail_account_id: 55,
  provider: 'yandex',
  status: 'paused_for_review',
  stage: 3,
  stage_limit: 50,
  manual_stage_approval: true,
  planned: 130,
  eligible: 130,
  excluded: 0,
  queued: 83,
  waiting: 0,
  attempted: 46,
  accepted: 45,
  accepted_in_campaign: 44,
  accepted_reconciled: 1,
  accepted_by_provider: { yandex: 44, mailru: 1 },
  failed_permanent: 2,
  failed_transient: 0,
  historical_disputed_transient: 2,
  delivery_unknown: 0,
  suppressed: 0,
  cancelled: 0,
  remaining: 83,
  provider_rejection_count: 2,
  health: { permanent_failure_rate: 0.015, transient_failure_rate: 0, unknown_rate: 0, provider_rejection_rate: 0.015, hard_bounces: 0 },
  pause_reason: 'stage_review',
  provider_warning: 'Яндекс может ограничивать массовую однотипную рассылку с обычного почтового ящика.',
  updated_at: '2026-08-29T10:00:00+00:00',
  excluded_targets: [],
};

async function mockRoutes(page: Page, options: { settingsAccounts?: typeof yandexAccount[]; campaignAccounts?: typeof yandexAccount[] } = {}) {
  let settingsAccounts = options.settingsAccounts ?? [yandexAccount];
  const connectPayloads: unknown[] = [];
  const continuationPayloads: unknown[] = [];
  const syncCalls: unknown[] = [];

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let payload: unknown = { ok: true };

    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'buyer@example.com', display_name: 'Снабжение', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/dashboard/summary') {
      payload = { kpis: { active_requests: 1, searching_requests: 0, new_replies: 0, attention: 0, unmatched_mail: 0 }, requests: [] };
    } else if (url.pathname === '/api/enrichment/step') {
      payload = { ok: true, processed: false, status: 'idle' };
    } else if (url.pathname === '/api/mail/status') {
      const first = settingsAccounts[0] ?? yandexAccount;
      payload = { connected: settingsAccounts.length > 0, provider: first.provider, email: first.email, status: first.status, last_error: first.last_error, updated_at: first.updated_at, accounts: settingsAccounts };
    } else if (url.pathname === '/api/mail/template') {
      payload = { subject: 'Запрос коммерческого предложения', body: 'Добрый день!\n\nПросим предоставить коммерческое предложение.', attachments: [], updated_at: '2026-08-29T10:00:00+00:00' };
    } else if (url.pathname === '/api/mail/accounts') {
      payload = { items: options.campaignAccounts ?? settingsAccounts };
    } else if (url.pathname === '/api/mail/accounts/mailru/connect') {
      const body = JSON.parse(request.postData() ?? '{}') as { email?: string; app_password?: string };
      connectPayloads.push(body);
      settingsAccounts = [yandexAccount, { ...mailruAccount, email: body.email ?? mailruAccount.email }];
      payload = { ok: true, account: settingsAccounts[1] };
    } else if (url.pathname === '/api/mail/sync') {
      syncCalls.push(JSON.parse(request.postData() ?? '{}'));
    } else if (url.pathname === '/api/mail/campaigns/7001') {
      payload = campaignSummary;
    } else if (url.pathname === '/api/requests/1099') {
      payload = requestDetail;
    } else if (url.pathname === '/api/mail/campaigns/7001/continuation-dry-run') {
      continuationPayloads.push(JSON.parse(request.postData() ?? '{}'));
      payload = {
        dry_run: true,
        campaign_id: 7001,
        campaign_provider: 'yandex',
        campaign_status: 'paused_for_review',
        current_mail_account_id: 55,
        target_mail_account_id: 56,
        target_provider: 'mailru',
        target_account_status: 'connected',
        target_email: 'buyer@mail.ru',
        eligible_untouched: 83,
        would_create: 83,
        would_send_now: 0,
        accepted_not_repeated: 45,
        failed_not_repeated: 2,
        delivery_unknown_not_repeated: 0,
        queued_in_current_campaign: 83,
        cancelled_not_repeated: 0,
        excluded_not_repeated: 0,
        safe: true,
        no_live_send: true,
        target_account: mailruAccount,
      };
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  return { connectPayloads, continuationPayloads, syncCalls };
}

async function expectNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

test('Settings connects Mail.ru with an app password and clears the form secret', async ({ page }, testInfo) => {
  const calls = await mockRoutes(page);
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Добавить Mail.ru' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('settings-mailru-before-connect.png'), fullPage: false });

  await page.getByPlaceholder('name@mail.ru').fill('buyer@mail.ru');
  const password = page.getByPlaceholder('Не обычный пароль');
  await password.fill('app-password-test');
  await page.getByRole('button', { name: 'Подключить Mail.ru' }).click();
  await expect(page.getByText('Mail.ru подключён. Пароль приложения больше не хранится в форме.')).toBeVisible();
  await expect(password).toHaveValue('');
  await expect(page.getByText('buyer@mail.ru', { exact: true })).toBeVisible();
  expect(calls.connectPayloads).toEqual([{ email: 'buyer@mail.ru', app_password: 'app-password-test' }]);
  await expectNoHorizontalOverflow(page);
  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('settings-mailru-connected.png'), fullPage: false });
});

test('Campaign continuation exposes a read-only Mail.ru dry-run with no send action', async ({ page }, testInfo) => {
  const calls = await mockRoutes(page, { campaignAccounts: [yandexAccount, mailruAccount] });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  const dryRunButton = page.getByRole('button', { name: 'Проверить без отправки' });
  await expect(dryRunButton).toBeEnabled();
  await dryRunButton.click();
  await expect(page.getByText('Dry-run завершён. Ничего не создано, не поставлено в очередь и не отправлено.')).toBeVisible();
  await expect(page.getByText('Будет подготовлено')).toBeVisible();
  await expect(page.getByText('83', { exact: true }).first()).toBeVisible();
  const accounting = page.locator('[data-provider-neutral-accounting]');
  await expect(accounting).toHaveText(/Yandex — 44 · Mail\.ru — 1 · всего 45/);
  expect(calls.continuationPayloads).toEqual([{ mail_account_id: 56 }]);
  await expectNoHorizontalOverflow(page);
  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('campaign-mailru-continuation-dry-run.png'), fullPage: false });
  await accounting.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('campaign-mailru-provider-accounting.png'), fullPage: false });
});

test('UI-MAIL-1 shows healthy incoming status separately from account configuration', async ({ page }, testInfo) => {
  await mockRoutes(page, { settingsAccounts: [{ ...yandexAccount, incoming_health: 'healthy' }] });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByText('Подключён', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Работают', { exact: true })).toBeVisible();
  await expect(page.getByText(/Последняя проверка:/)).toBeVisible();
  await expect(page.getByText('Ошибка синхронизации', { exact: true })).toHaveCount(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath('settings-mail-health-healthy.png'), fullPage: false });
});

test('UI-MAIL-2 shows incoming error and a retry action', async ({ page }, testInfo) => {
  const failed = { ...yandexAccount, incoming_health: 'error', incoming_last_error: 'Не удалось подключиться к IMAP-серверу Яндекса.', last_error: 'Не удалось подключиться к IMAP-серверу Яндекса.' };
  await mockRoutes(page, { settingsAccounts: [failed] });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByText('Ошибка синхронизации', { exact: true })).toBeVisible();
  await expect(page.getByText('Ошибка входящих: Не удалось подключиться к IMAP-серверу Яндекса.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Повторить входящие' })).toBeVisible();
  await expect(page.getByText('Подключён', { exact: true }).first()).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath('settings-mail-health-error.png'), fullPage: false });
});

test('UI-MAIL-3 clears a stale incoming error after successful retry', async ({ page }) => {
  let hasFailed = true;
  const failed = { ...yandexAccount, incoming_health: 'error', incoming_last_error: 'Сбой IMAP', last_error: 'Сбой IMAP' };
  const healthy = { ...yandexAccount, incoming_health: 'healthy', incoming_last_error: null, last_error: null };
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/auth/me') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, csrf_token: 'audit-token', user: { email: 'buyer@example.com', display_name: 'Снабжение', workspace_name: 'SupplyDesk' } }) });
      return;
    }
    if (url.pathname === '/api/mail/status') {
      const account = hasFailed ? failed : healthy;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ connected: true, provider: 'yandex', email: account.email, status: account.status, accounts: [account] }) });
      return;
    }
    if (url.pathname === '/api/mail/template') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ subject: 'Тема', body: 'Текст', attachments: [], updated_at: null }) });
      return;
    }
    if (url.pathname === '/api/mail/sync') {
      hasFailed = false;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, imported: 0 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByText('Ошибка синхронизации', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Повторить входящие' }).click();
  await expect(page.getByText('Работают', { exact: true })).toBeVisible();
  await expect(page.getByText('Ошибка синхронизации', { exact: true })).toHaveCount(0);
});

test('UI-MAIL-4 keeps Mail.ru healthy when Yandex incoming sync fails', async ({ page }) => {
  const accounts = [
    { ...yandexAccount, incoming_health: 'error', incoming_last_error: 'Yandex IMAP fail', last_error: 'Yandex IMAP fail' },
    { ...mailruAccount, incoming_health: 'healthy' },
  ];
  await mockRoutes(page, { settingsAccounts: accounts });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByText('Ошибка входящих: Yandex IMAP fail', { exact: true })).toBeVisible();
  await expect(page.getByText('Работают', { exact: true })).toBeVisible();
  await expect(page.getByText('buyer@mail.ru', { exact: true })).toBeVisible();
});

test('UI-MAIL-5 keeps Yandex healthy when Mail.ru incoming sync fails', async ({ page }) => {
  const accounts = [
    { ...yandexAccount, incoming_health: 'healthy', incoming_last_error: null },
    { ...mailruAccount, incoming_health: 'error', incoming_last_error: 'Mail.ru IMAP fail', last_error: 'Mail.ru IMAP fail' },
  ];
  await mockRoutes(page, { settingsAccounts: accounts });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expect(page.getByText('Ошибка входящих: Mail.ru IMAP fail', { exact: true })).toBeVisible();
  await expect(page.getByText('Работают', { exact: true })).toBeVisible();
  await expect(page.getByText('buyer@example.com', { exact: true })).toBeVisible();
});

test('UI-MAIL-6 keeps the status cards usable on portrait mobile', async ({ page }, testInfo) => {
  test.skip(!['mobile-large', 'mobile-small'].includes(testInfo.project.name), 'mobile-only acceptance');
  await mockRoutes(page, { settingsAccounts: [yandexAccount, mailruAccount] });
  await page.goto('/settings', { waitUntil: 'networkidle' });
  await expectNoHorizontalOverflow(page);
  await expect(page.getByText('Работают', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Синхронизировать входящие' }).first()).toBeVisible();
});
