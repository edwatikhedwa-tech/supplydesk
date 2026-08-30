import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const requestItem = {
  id: 1099,
  name: 'Кампания для проверки поставщиков',
  description: 'Проверка материалов для проекта.',
  deadline: '',
  sender_name: 'Снабжение',
  company_name: 'SupplyDesk',
  created_at: '2026-08-28T10:00:00+00:00',
  status: 'completed',
  search_progress: 1,
  search_total: 1,
  search_depth: 1,
  last_error: null,
  updated_at: '2026-08-28T10:01:00+00:00',
  positions_count: 1,
  suppliers_count: 2,
  sent_count: 0,
  replies_count: 0,
};

const suppliers = [
  {
    id: 9901,
    external_key: 'acme.example',
    name: 'ООО «Акме»',
    email: 'sales@acme.example',
    host: 'acme.example',
    inn: '7700000001',
    inn_source: 'auto',
    kind: 'company',
    region: 'Москва',
    role: 'производитель',
    phone: '+7 495 000-00-01',
    reason: 'Найдено по заявке',
    source: 'web',
    found_url: 'https://acme.example',
    covers: ['p1'],
    position_keys: ['p1'],
    site_unavailable: 0,
    mail_status: 'not_sent',
    last_error: null,
    registry: null,
    finances: null,
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  },
  {
    id: 9902,
    external_key: 'north.example',
    name: 'ООО «Северный поставщик с длинным названием»',
    email: 'offers@north.example',
    host: 'north.example',
    inn: '7700000002',
    inn_source: 'auto',
    kind: 'company',
    region: 'Санкт-Петербург',
    role: 'производитель',
    phone: '+7 812 000-00-02',
    reason: 'Найдено по заявке',
    source: 'web',
    found_url: 'https://north.example',
    covers: ['p1'],
    position_keys: ['p1'],
    site_unavailable: 0,
    mail_status: 'not_sent',
    last_error: null,
    registry: null,
    finances: null,
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  },
];

type TestSupplier = (typeof suppliers)[number];

function sizeTestSuppliers(count: number): TestSupplier[] {
  return Array.from({ length: count }, (_, index) => ({
    ...suppliers[0],
    id: 10000 + index,
    external_key: `size-test-${index}.example`,
    name: `Тестовый поставщик ${index + 1}`,
    email: `contact-${index + 1}@size-test.example`,
    host: 'size-test.example',
  }));
}

const basePreflight = {
  ok: true,
  dry_run: true,
  preview: false,
  preview_contract: { frozen: false, renderer: 'operation_target_snapshot', snapshot_frozen_on: 'send-bulk operation assembly', rerun_if_source_data_changed: true },
  status: 'PASS',
  planned: 2,
  eligible: 2,
  excluded: 0,
  unique_domains: 2,
  recipient_results: suppliers.map((supplier) => ({ email: supplier.email, domain: supplier.host, status: 'eligible', reasons: [], personalization_level: 1 })),
  warnings: [],
  blocks: [],
  personalization_distribution: { '1': 2 },
  similarity_ratio: 0.22,
  attachment_total_bytes: 0,
  provider: 'yandex',
  provider_warning: 'Яндекс может ограничивать массовую отправку однотипных коммерческих писем с обычного почтового ящика.',
  campaign_limits: { max_recipients: 300 },
  account_budget: { max_per_hour: 100, max_per_day: 100 },
  pacing: { min_interval_seconds: 30, max_interval_seconds: 60 },
  budget_warning: null,
  estimated_duration_seconds: { minimum: 30, average: 45, maximum: 60 },
  rollout: { stage_1: 10, stage_2: 25, stage_3: 50, manual_stage_approval: true },
  previews: [
    { normalized_email: 'sales@acme.example', supplier_id: 9901, to_email: 'sales@acme.example', subject: 'Запрос для ООО «Акме»', body_text: 'Здравствуйте, ООО «Акме»!\n\nПросим предоставить предложение.', body_html: '<p>Здравствуйте, ООО «Акме»!</p>', message_id_header: '<preview-1@example.com>', personalization_level: 1 },
    { normalized_email: 'offers@north.example', supplier_id: 9902, to_email: 'offers@north.example', subject: 'Запрос для ООО «Северный поставщик с длинным названием»', body_text: 'Здравствуйте, ООО «Северный поставщик с длинным названием»!\n\nПросим предоставить предложение.', body_html: '<p>Здравствуйте, поставщик!</p>', message_id_header: '<preview-2@example.com>', personalization_level: 1 },
  ],
};

const campaignSummary = {
  campaign_id: 7001,
  operation_id: 8001,
  request_id: 1099,
  mail_account_id: 55,
  provider: 'yandex',
  status: 'paused_for_review',
  stage: 1,
  stage_limit: 2,
  manual_stage_approval: true,
  planned: 2,
  eligible: 2,
  excluded: 0,
  queued: 0,
  waiting: 0,
  attempted: 2,
  accepted: 2,
  failed_permanent: 0,
  failed_transient: 0,
  delivery_unknown: 0,
  suppressed: 0,
  cancelled: 0,
  remaining: 1,
  provider_rejection_count: 0,
  health: { permanent_failure_rate: 0, transient_failure_rate: 0, unknown_rate: 0, provider_rejection_rate: 0, hard_bounces: 0 },
  pause_reason: 'stage_review',
  provider_warning: basePreflight.provider_warning,
  updated_at: '2026-08-28T10:02:00+00:00',
  excluded_targets: [],
};

type CampaignRouteOptions = {
  preflightSequence?: Array<Partial<typeof basePreflight>>;
  campaignSequence?: Array<Partial<typeof campaignSummary>>;
  campaignSummaryOverride?: Partial<typeof campaignSummary>;
  sendBulkFailsOnce?: boolean;
  supplierList?: TestSupplier[];
};

async function setupCampaignRoutes(page: Page, mode: 'pass' | 'warning' | 'block' = 'pass', options: CampaignRouteOptions = {}) {
  let sendBulkCalls = 0;
  let preflightCalls = 0;
  let previewCalls = 0;
  let campaignGetCalls = 0;
  const sendBulkPayloads: unknown[] = [];
  const preflightPayloads: unknown[] = [];
  const actionCalls: string[] = [];
  const requestSuppliers = options.supplierList ?? suppliers;
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let payload: unknown = { ok: true };
    const status = 200;
    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'buyer@example.com', display_name: 'Снабжение', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/dashboard/summary') {
      payload = { kpis: { active_requests: 1, searching_requests: 0, new_replies: 0, attention: 0, unmatched_mail: 0 }, requests: [] };
    } else if (url.pathname === '/api/enrichment/step') {
      payload = { ok: true, processed: false, status: 'idle' };
    } else if (url.pathname === '/api/requests/1099') {
      payload = { request: { ...requestItem, suppliers_count: requestSuppliers.length }, positions: [{ id: 1, request_id: 1099, position_key: 'p1', name: 'Профиль стальной', quantity: '10', created_at: requestItem.created_at }], items: requestSuppliers };
    } else if (url.pathname === '/api/mail/status') {
      payload = {
        connected: true,
        provider: 'yandex',
        email: 'buyer@example.com',
        status: 'connected',
        last_error: null,
        updated_at: requestItem.updated_at,
        accounts: [
          { id: 55, provider: 'yandex', email: 'buyer@example.com', auth_mode: 'oauth', status: 'connected', connected: true, outgoing_enabled: true, incoming_enabled: true, last_error: null, updated_at: requestItem.updated_at },
          { id: 56, provider: 'mailru', email: 'buyer@mail.ru', auth_mode: 'app_password', credential_reference: 'mailru-account:56', status: 'connected', connected: true, outgoing_enabled: true, incoming_enabled: true, last_error: null, updated_at: requestItem.updated_at },
        ],
      };
    } else if (url.pathname === '/api/mail/template') {
      payload = { subject: 'Запрос для {{supplier_name}}', body: 'Здравствуйте, {{supplier_name}}!\n\nПросим предоставить предложение.', attachments: [], updated_at: requestItem.updated_at };
    } else if (url.pathname === '/api/mail/deliverability/preflight') {
      preflightCalls += 1;
      preflightPayloads.push(JSON.parse(request.postData() ?? 'null'));
      if (options.preflightSequence?.length) payload = { ...basePreflight, ...options.preflightSequence[Math.min(preflightCalls - 1, options.preflightSequence.length - 1)] };
      else if (mode === 'block') payload = { ...basePreflight, status: 'BLOCK', eligible: 1, excluded: 1, blocks: ['suppressed'], warnings: [], recipient_results: [{ ...basePreflight.recipient_results[0], status: 'excluded', reasons: ['suppressed'] }, basePreflight.recipient_results[1]] };
      else if (mode === 'warning') payload = { ...basePreflight, status: 'WARNING', warnings: ['provider_policy_warning', 'high_content_similarity'], provider_warning: basePreflight.provider_warning };
      else payload = basePreflight;
    } else if (url.pathname === '/api/mail/deliverability/preview') {
      previewCalls += 1;
      payload = { ...basePreflight, preview: true };
    } else if (url.pathname === '/api/mail/send-bulk') {
      sendBulkCalls += 1;
      sendBulkPayloads.push(JSON.parse(request.postData() ?? 'null'));
      if (options.sendBulkFailsOnce && sendBulkCalls === 1) {
        payload = { ok: false, error: 'Временная ошибка тестового API.' };
      } else {
        payload = { ok: true, queued: [{ job_id: 9001, message_id: 9002, thread_id: 9003, operation_id: 8001, campaign_id: 7001 }] };
      }
    } else if (url.pathname === '/api/mail/campaigns/7001') {
      campaignGetCalls += 1;
      const sequenceItem = options.campaignSequence?.[Math.min(campaignGetCalls - 1, (options.campaignSequence?.length ?? 1) - 1)] ?? {};
      payload = { ...campaignSummary, ...options.campaignSummaryOverride, ...sequenceItem };
    } else if (url.pathname === '/api/mail/campaigns/7001/resume' || url.pathname === '/api/mail/campaigns/7001/pause' || url.pathname === '/api/mail/campaigns/7001/stop') {
      actionCalls.push(url.pathname);
      payload = { ok: true, ...campaignSummary, ...options.campaignSummaryOverride, status: url.pathname.endsWith('/stop') ? 'stopped' : url.pathname.endsWith('/pause') ? 'paused_for_review' : 'active', pause_reason: url.pathname.endsWith('/stop') ? 'stopped_by_user' : url.pathname.endsWith('/pause') ? 'manual_pause' : null };
    }
    await route.fulfill({ status: options.sendBulkFailsOnce && url.pathname === '/api/mail/send-bulk' && sendBulkCalls === 1 ? 500 : status, contentType: 'application/json', body: JSON.stringify(payload) });
  });
  return { get sendBulkCalls() { return sendBulkCalls; }, get preflightCalls() { return preflightCalls; }, get previewCalls() { return previewCalls; }, get campaignGetCalls() { return campaignGetCalls; }, sendBulkPayloads, preflightPayloads, actionCalls };
}

async function openComposer(page: Page) {
  await page.goto('/requests/1099', { waitUntil: 'networkidle' });
  await page.getByRole('checkbox', { name: 'Выбрать поставщика' }).first().click();
  await page.getByRole('button', { name: 'Подготовить запрос' }).click();
  await expect(page.getByRole('dialog', { name: 'Подготовка рассылки' })).toBeVisible();
}

async function openComposerWithAllEmailRecipients(page: Page) {
  await page.goto('/requests/1099', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Выбрать всех с email' }).click({ force: true });
  await page.getByRole('button', { name: 'Подготовить запрос' }).click();
  await expect(page.getByRole('dialog', { name: 'Подготовка рассылки' })).toBeVisible();
}

async function expectNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

test('campaign bulk flow requires preflight, renders exact preview and keeps idempotency on start', async ({ page }, testInfo) => {
  const calls = await setupCampaignRoutes(page);
  await openComposer(page);
  await expect(page.getByRole('button', { name: 'Проверить рассылку' })).toBeVisible();
  expect(calls.sendBulkCalls).toBe(0);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(page.getByText('Можно запускать')).toBeVisible();
  expect(calls.preflightCalls).toBe(1);
  expect(calls.sendBulkCalls).toBe(0);
  await page.getByRole('button', { name: 'Открыть просмотр' }).click();
  await expect(page.getByText('Запрос для ООО «Акме»')).toBeVisible();
  await page.getByRole('dialog', { name: 'Подготовка рассылки' }).locator('div.flex-1.overflow-y-auto').evaluate((element) => { element.scrollTop = 0; });
  await page.screenshot({ path: testInfo.outputPath('campaign-preflight-preview.png'), fullPage: false });
  expect(calls.previewCalls).toBe(1);
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await expect(page.getByText('Будет создана кампания')).toBeVisible();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page).toHaveURL(/\/mail\/campaigns\/7001$/);
  expect(calls.preflightCalls).toBe(2);
  expect(calls.sendBulkCalls).toBe(1);
  expect((calls.sendBulkPayloads[0] as { manual_stage_approval: boolean }).manual_stage_approval).toBe(true);
  expect(await page.locator('body').innerText()).not.toContain('Доставлено');
  await page.screenshot({ path: testInfo.outputPath('campaign-detail-after-start.png'), fullPage: false });
});

test('per-campaign approval checkbox reflects backend default and is sent in the intent', async ({ page }, testInfo) => {
  const calls = await setupCampaignRoutes(page);
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  const approval = page.getByRole('checkbox', { name: 'Подтверждать каждый этап вручную' });
  await expect(approval).toBeChecked();
  await approval.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('campaign-approval-checkbox.png'), fullPage: false });
  await approval.uncheck();
  await expect(approval).not.toBeChecked();
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await expect(page.getByText('Этапы продолжаются автоматически при нормальном состоянии кампании.')).toBeVisible();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page).toHaveURL(/\/mail\/campaigns\/7001$/);
  expect((calls.sendBulkPayloads[0] as { manual_stage_approval: boolean }).manual_stage_approval).toBe(false);
});

test('changing approval mode creates a new idempotent intent', async ({ page }) => {
  const calls = await setupCampaignRoutes(page, 'pass', { sendBulkFailsOnce: true });
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  const approval = page.getByRole('checkbox', { name: 'Подтверждать каждый этап вручную' });
  await approval.uncheck();
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page.getByRole('alert')).toContainText('Временная ошибка тестового API.');
  await page.getByRole('button', { name: 'Назад', exact: true }).click();
  await approval.check();
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page).toHaveURL(/\/mail\/campaigns\/7001$/);
  expect(calls.sendBulkPayloads).toHaveLength(2);
  expect((calls.sendBulkPayloads[0] as { manual_stage_approval: boolean }).manual_stage_approval).toBe(false);
  expect((calls.sendBulkPayloads[1] as { manual_stage_approval: boolean }).manual_stage_approval).toBe(true);
  expect((calls.sendBulkPayloads[0] as { idempotency_key: string }).idempotency_key).not.toBe((calls.sendBulkPayloads[1] as { idempotency_key: string }).idempotency_key);
});

test('warning needs acknowledgement before continuing', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page, 'warning');
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(page.getByText('Большая часть писем практически одинакова.')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('campaign-warning.png'), fullPage: false });
  const continueButton = page.getByRole('button', { name: 'Перейти к запуску' });
  await expect(continueButton).toBeDisabled();
  await page.getByText('Я проверил предупреждения и хочу продолжить.').click();
  await expect(continueButton).toBeEnabled();

});

test('BLOCK explains the issue and does not expose a launch action', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page, 'block');
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(page.getByText('Запуск заблокирован')).toBeVisible();
  await expect(page.getByText('Адрес в списке «не писать»').first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('campaign-block.png'), fullPage: false });
  await expect(page.getByRole('button', { name: 'Перейти к запуску' })).toHaveCount(0);
});

test('UI6 final preflight change returns to review without send', async ({ page }) => {
  const calls = await setupCampaignRoutes(page, 'pass', {
    preflightSequence: [
      basePreflight,
      { status: 'BLOCK', eligible: 1, excluded: 1, blocks: ['suppressed'], recipient_results: [{ ...basePreflight.recipient_results[0], status: 'excluded', reasons: ['suppressed'] }, basePreflight.recipient_results[1]] },
    ],
  });
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await page.getByRole('button', { name: 'Открыть просмотр' }).click();
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page.getByText('Запуск заблокирован')).toBeVisible();
  await expect(page.getByText('Проверка перед запуском нашла новую блокирующую причину. Ничего не отправлено.')).toBeVisible();
  expect(calls.sendBulkCalls).toBe(0);
});

test('UI7 double click creates one intent and UI8 retry keeps the same idempotency key', async ({ page }) => {
  const calls = await setupCampaignRoutes(page, 'pass', { sendBulkFailsOnce: true });
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await page.getByRole('button', { name: 'Открыть просмотр' }).click();
  await page.getByRole('button', { name: 'Перейти к запуску' }).click();
  await page.getByRole('button', { name: 'Запустить кампанию' }).click();
  await expect(page.getByRole('alert')).toContainText('Временная ошибка тестового API.');
  await page.getByRole('button', { name: 'Запустить кампанию' }).dblclick();
  await expect(page).toHaveURL(/\/mail\/campaigns\/7001$/);
  expect(calls.sendBulkCalls).toBe(2);
  const first = calls.sendBulkPayloads[0] as { idempotency_key: string };
  const second = calls.sendBulkPayloads[1] as { idempotency_key: string };
  expect(first.idempotency_key).toBeTruthy();
  expect(second.idempotency_key).toBe(first.idempotency_key);
});

test('UI12 resume uses campaign action and does not create another send-bulk', async ({ page }) => {
  const calls = await setupCampaignRoutes(page);
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Продолжить следующий этап' }).click();
  await page.getByRole('button', { name: 'Да, продолжить' }).click();
  await expect(page.getByText('Следующий этап разрешён.')).toBeVisible();
  expect(calls.actionCalls).toEqual(['/api/mail/campaigns/7001/resume']);
  expect(calls.sendBulkCalls).toBe(0);
});

test('UI13 health pause shows reason and UI14 pause uses the correct API', async ({ page }) => {
  const healthCalls = await setupCampaignRoutes(page, 'pass', { campaignSummaryOverride: { status: 'paused_for_health', pause_reason: 'provider_spam_or_policy_rejection', remaining: 1 } });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByText('Приостановлена из-за проблем')).toBeVisible();
  await expect(page.getByText('Провайдер сообщил об ограничении политики или подозрении на нежелательную рассылку.').last()).toBeVisible();
  expect(healthCalls.actionCalls).toHaveLength(0);

  const pauseCalls = await setupCampaignRoutes(page, 'pass', { campaignSummaryOverride: { status: 'active', pause_reason: null, remaining: 1 } });
  await page.reload({ waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Пауза' }).click();
  await expect(page.getByText('Кампания поставлена на паузу.')).toBeVisible();
  expect(pauseCalls.actionCalls).toEqual(['/api/mail/campaigns/7001/pause']);
});

test('UI35 manual pause keeps the current stage and uses manual-pause wording', async ({ page }, testInfo) => {
  const calls = await setupCampaignRoutes(page, 'pass', { campaignSummaryOverride: { status: 'active', pause_reason: null, remaining: 1 } });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Пауза' }).click();
  await expect(page.getByRole('heading', { name: 'Кампания на паузе' }).last()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продолжить текущий этап' })).toBeVisible();
  await expect(page.getByText(/Этап завершён/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('campaign-manual-pause.png'), fullPage: false });
  await page.getByRole('button', { name: 'Продолжить текущий этап' }).click();
  await expect(page.getByRole('dialog', { name: 'Продолжить текущий этап?' })).toBeVisible();
  await page.getByRole('button', { name: 'Да, продолжить' }).click();
  await expect(page.getByText('Текущий этап продолжен.')).toBeVisible();
  expect(calls.actionCalls).toEqual(['/api/mail/campaigns/7001/pause', '/api/mail/campaigns/7001/resume']);
});

test('UI36 stage review keeps completed-stage wording', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page);
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Этап завершён — проверьте результат' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продолжить следующий этап' })).toBeVisible();
  await expect(page.getByText('Кампания на паузе')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('campaign-stage-review.png'), fullPage: false });
});

test('UI37 preflight mode text follows the changed checkbox immediately', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page, 'pass');
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  const approval = page.getByRole('checkbox', { name: 'Подтверждать каждый этап вручную' });
  await expect(approval).toBeChecked();
  await approval.uncheck();
  await expect(page.getByText(/Режим проверки этапов: автоматическое продолжение/)).toBeVisible();
  await expect(page.getByText(/Режим проверки этапов: ручное подтверждение/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('composer-mode-auto.png'), fullPage: false });
});

test('UI38 preflight mode text follows enabling a false backend default', async ({ page }) => {
  await setupCampaignRoutes(page, 'pass', { preflightSequence: [{ rollout: { ...basePreflight.rollout, manual_stage_approval: false } }] });
  await openComposer(page);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  const approval = page.getByRole('checkbox', { name: 'Подтверждать каждый этап вручную' });
  await expect(approval).not.toBeChecked();
  await approval.check();
  await expect(page.getByText(/Режим проверки этапов: ручное подтверждение/)).toBeVisible();
  await expect(page.getByText(/Режим проверки этапов: автоматическое продолжение/)).toHaveCount(0);
});

test('UI16 stopped campaign has no resume and UI18 delivery_unknown is separate', async ({ page }) => {
  await setupCampaignRoutes(page, 'pass', { campaignSummaryOverride: { status: 'stopped', pause_reason: 'stopped_by_user', remaining: 1 } });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: 'Остановлена' })).toBeVisible();
  await expect(page.getByText('Кампания остановлена. Возобновить её нельзя.')).toBeVisible();
  await expect(page.getByRole('button', { name: /Продолжить/ })).toHaveCount(0);

  await page.route('**/api/mail/campaigns/7001', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...campaignSummary, status: 'paused_for_review', pause_reason: 'stage_review', delivery_unknown: 1, remaining: 1 }) });
  });
  await page.reload({ waitUntil: 'networkidle' });
  await expect(page.getByText('Есть отправки, требующие проверки · 1')).toBeVisible();
  await expect(page.getByText('SupplyDesk не отправит их повторно автоматически.')).toBeVisible();
});

test('UI21 polling stops after terminal campaign status', async ({ page }) => {
  const calls = await setupCampaignRoutes(page, 'pass', {
    campaignSequence: [
      { status: 'active', accepted: 0, attempted: 0, remaining: 2 },
      { status: 'completed', accepted: 2, attempted: 2, remaining: 0 },
    ],
  });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByText('Выполняется')).toBeVisible();
  await page.waitForTimeout(4300);
  await expect(page.getByText('Завершена')).toBeVisible();
  const terminalCalls = calls.campaignGetCalls;
  await page.waitForTimeout(1000);
  expect(calls.campaignGetCalls).toBe(terminalCalls);
});

test('campaign detail exposes paused review, health metrics, stop confirmation and mobile layout', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page);
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByText('Ожидает подтверждения')).toBeVisible();
  await expect(page.getByLabel('Показатели кампании').getByText('Отправлено')).toBeVisible();
  await expect(page.getByText('Этап 1 · до 2')).toBeVisible();
  await expect(page.getByText('Этапы подтверждаются вручную.')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Подтверждать каждый этап вручную' })).toHaveCount(0);
  await page.getByText('Этапы подтверждаются вручную.').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('campaign-detail-rollout-mode.png'), fullPage: false });
  await page.getByRole('button', { name: 'Остановить оставшиеся' }).click();
  await expect(page.getByRole('dialog', { name: 'Остановить оставшиеся письма?' })).toBeVisible();
  await expect(page.getByText('Уже отправленные письма и неопределённые отправки останутся в истории.')).toBeVisible();
  await page.getByRole('button', { name: 'Отмена' }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath('campaign-detail-paused-review.png'), fullPage: false });
  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations).toEqual([]);
  const geometry = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth + 1);
});

test('campaign detail uses persisted automatic mode wording', async ({ page }) => {
  await setupCampaignRoutes(page, 'pass', { campaignSummaryOverride: { manual_stage_approval: false } });
  await page.goto('/mail/campaigns/7001', { waitUntil: 'networkidle' });
  await expect(page.getByText('Этапы продолжаются автоматически при нормальном состоянии кампании.')).toBeVisible();
  await expect(page.getByText('Этапы подтверждаются вручную.')).toHaveCount(0);
});

test('UI39/UI43 accepts a 120-recipient dry-run and shows the account budget warning', async ({ page }, testInfo) => {
  await setupCampaignRoutes(page, 'pass', {
    supplierList: sizeTestSuppliers(120),
    preflightSequence: [{
      status: 'WARNING',
      planned: 120,
      eligible: 120,
      warnings: ['campaign_exceeds_daily_budget'],
      budget_warning: 'Кампания содержит 120 получателей, а текущий rolling 24-часовой бюджет аккаунта — 100. После исчерпания бюджета оставшиеся письма будут ждать открытия нового окна.',
      estimated_duration_seconds: { minimum: 3570, average: 5355, maximum: 7140 },
    }],
  });
  await openComposerWithAllEmailRecipients(page);
  await expect(page.getByText('120', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(page.getByText('Нужна проверка')).toBeVisible();
  await expect(page.getByText('Максимум кампании').locator('..')).toContainText('300');
  await expect(page.getByText('Ограничение бюджета аккаунта')).toBeVisible();
  await expect(page.getByText(/Кампания содержит 120 получателей/)).toBeVisible();
  await expect(page.getByText('campaign_size_out_of_range')).toHaveCount(0);
  await expect(page.getByText('около 1 ч 29 мин.')).toBeVisible();
  await expect(page.getByText('Диапазон: 1 ч – 1 ч 59 мин.')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('NaN');
  await expect(page.locator('body')).not.toContainText('undefined');
  await expect(page.locator('body')).not.toContainText('[object Object]');
  await page.screenshot({ path: testInfo.outputPath('campaign-120-preflight.png'), fullPage: false });
});

test('UI40/UI41 keeps 301 selected recipients visible and blocks without silent truncation', async ({ page }) => {
  await setupCampaignRoutes(page, 'pass', {
    supplierList: sizeTestSuppliers(301),
    preflightSequence: [{ status: 'BLOCK', planned: 301, eligible: 301, blocks: ['campaign_size_out_of_range'] }],
  });
  await openComposerWithAllEmailRecipients(page);
  const dialog = page.getByRole('dialog', { name: 'Подготовка рассылки' });
  const recipientLabels = dialog.locator('section[aria-labelledby="campaign-recipients-title"] label');
  await expect(recipientLabels).toHaveCount(301);
  await expect(dialog.getByText('301', { exact: true }).first()).toBeVisible();
  const checkedBefore = await recipientLabels.locator('input[type="checkbox"]:checked').count();
  expect(checkedBefore).toBe(301);
  await dialog.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(dialog.getByText('Запуск заблокирован')).toBeVisible();
  await expect(dialog.getByText('Выбрано 301. Максимум для одной кампании — 300.')).toBeVisible();
  await expect(dialog.getByText('Уберите ещё 1 получателя.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Изменить письмо' }).click();
  await expect(recipientLabels).toHaveCount(301);
  expect(await recipientLabels.locator('input[type="checkbox"]:checked').count()).toBe(301);
  await expect(dialog.getByRole('button', { name: 'Перейти к запуску' })).toHaveCount(0);
});

test('Mail.ru account can be selected before read-only preflight', async ({ page }, testInfo) => {
  const calls = await setupCampaignRoutes(page);
  await openComposer(page);
  const account = page.getByLabel('Почтовый аккаунт');
  await expect(account).toHaveValue('55');
  await account.selectOption('56');
  await expect(account).toHaveValue('56');
  await page.screenshot({ path: testInfo.outputPath('composer-mailru-account.png'), fullPage: false });
  await expectNoHorizontalOverflow(page);
  const axeResults = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
  expect(axeResults.violations).toEqual([]);
  await page.getByRole('button', { name: 'Проверить рассылку' }).click();
  await expect(page.getByText('Можно запускать')).toBeVisible();
  expect((calls.preflightPayloads[0] as { mail_account_id: number }).mail_account_id).toBe(56);
});
