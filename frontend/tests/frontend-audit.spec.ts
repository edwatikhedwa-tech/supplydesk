import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

function formatAxeViolations(violations: Array<{ id: string; help: string; nodes: Array<{ target: unknown }> }>) {
  return violations
    .map((violation) => `${violation.id}: ${violation.help} (${violation.nodes.length} nodes)`)
    .join('\n');
}

async function expectNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);
}

test('public shell has no mobile overflow and passes accessibility checks', async ({ page }, testInfo) => {
  await page.goto('/login', { waitUntil: 'networkidle' });
  await page.addStyleTag({
    content: '*, *::before, *::after { animation: none !important; transition: none !important; }',
  });

  const geometry = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const isHidden = (element: Element) => {
      let current: Element | null = element;
      while (current) {
        if (current.getAttribute('aria-hidden') === 'true' || current.getAttribute('data-audit-ignore') === 'true') return true;
        current = current.parentElement;
      }
      return false;
    };
    const visible = (element: Element) => {
      if (isHidden(element)) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    };
    const outside = [...document.body.querySelectorAll('*')]
      .filter(visible)
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter(({ rect }) => rect.left < -1 || rect.right > viewportWidth + 1)
      .slice(0, 20)
      .map(({ element, rect }) => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className.slice(0, 120) : '',
        left: Math.round(rect.left),
        right: Math.round(rect.right),
      }));
    return {
      viewportWidth,
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      outside,
    };
  });

  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);
  expect(geometry.outside, JSON.stringify(geometry)).toEqual([]);

  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-login.png`),
    fullPage: true,
  });

  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations, formatAxeViolations(axeResults.violations)).toEqual([]);
});

test('unbound email stays readable after remote images are hidden and reply is immediately usable', async ({ page }, testInfo) => {
  const inboxMessage = {
    id: 6201,
    from_email: 'marketing@example.com',
    to_email: 'buyer@example.com',
    subject: 'Рассылка с большой картинкой',
    body_text: 'Привет!\nПервая строка\nВторая строка',
    body_html: `
      <table width="640" role="presentation">
        <tr><td height="900"><a href="https://tracker.example/open"><img data-remote-src="https://tracker.example/hero.png" width="640" height="900" alt=""></a></td></tr>
        <tr><td><p>Привет!<br>Первая строка<br>Вторая строка</p></td></tr>
      </table>`,
    received_at: '2026-08-28T14:00:00+00:00',
    status: 'received',
    has_remote_images: true,
  };
  let replyAttempts = 0;

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          authenticated: true,
          csrf_token: 'audit-token',
          user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
        }),
      });
      return;
    }
    if (url.pathname === '/api/mail/inbox') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [inboxMessage] }) });
      return;
    }
    if (url.pathname === `/api/mail/inbox/${inboxMessage.id}/suggestions`) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) });
      return;
    }
    if (url.pathname === '/api/mail/inbox/reply') {
      replyAttempts += 1;
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Тестовая ошибка отправки' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], kpis: { active_requests: 0, searching_requests: 0, new_replies: 0, attention: 0, unmatched_mail: 1 } }) });
  });

  await page.goto('/messages?tab=unmatched', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
  await page.getByRole('button', { name: /marketing@example\.com/ }).click();

  const emailFrame = page.locator('iframe[title="Содержимое письма"]');
  await expect(emailFrame).toBeVisible();
  const emailMetrics = await emailFrame.evaluate((element) => {
    const iframe = element as HTMLIFrameElement;
    const body = iframe.contentDocument?.body;
    return {
      frameHeight: Math.round(iframe.getBoundingClientRect().height),
      text: body?.innerText ?? '',
      lineBreaks: body?.querySelectorAll('br').length ?? 0,
      remoteImages: body?.querySelectorAll('img[data-remote-src]').length ?? 0,
    };
  });
  expect(emailMetrics.frameHeight, JSON.stringify(emailMetrics)).toBeLessThan(360);
  expect(emailMetrics.text).toContain('Первая строка');
  expect(emailMetrics.text).toContain('Вторая строка');
  expect(emailMetrics.lineBreaks).toBeGreaterThanOrEqual(2);
  expect(emailMetrics.remoteImages).toBe(0);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-unmatched-reader.png`), fullPage: false });

  await page.getByRole('button', { name: 'Ответить' }).click();
  const dialog = page.getByRole('dialog', { name: 'Ответить' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('Текст ответа')).toBeFocused();
  await dialog.getByLabel('Текст ответа').fill('Проверка ответа без внешней отправки.');
  await dialog.getByRole('button', { name: 'Отправить' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Не удалось отправить ответ');
  await expect(dialog.getByRole('button', { name: 'Отправить' })).toBeEnabled();
  expect(replyAttempts).toBe(1);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-unmatched-reader-and-reply.png`), fullPage: false });

  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations, formatAxeViolations(axeResults.violations)).toEqual([]);
});

test('matched correspondence preserves sender CSS and keeps a wide email inside the reader', async ({ page }, testInfo) => {
  const thread = {
    id: 9301,
    request_id: 1071,
    supplier_id: 5001,
    subject: 'Предложение по заявке',
    last_message_at: '2026-08-30T08:00:00+00:00',
    created_at: '2026-08-30T07:00:00+00:00',
    request_name: 'Проверка HTML-письма',
    supplier_name: 'ООО «Тестовый поставщик»',
    supplier_email: 'sales@example.com',
    supplier_host: 'example.com',
    supplier_external_key: 'test-5001',
    messages_count: 1,
    replies_count: 1,
    unread_count: 1,
  };
  const message = {
    id: 9302,
    direction: 'inbound',
    from_email: 'sales@example.com',
    to_email: 'buyer@example.com',
    subject: thread.subject,
    body_text: 'Готовы предложить решение. Открыть предложение.',
    body_html: `
      <style>
        .mail-card { background: #eef6ff; border: 2px solid #1769aa; border-radius: 14px; }
        .mail-title { color: #12395b; font-size: 22px; }
        .cta { background: #1769aa; color: #ffffff; border-radius: 8px; padding: 12px 20px; }
        @media screen and (max-width: 600px) { .mail-title { font-size: 18px; } }
      </style>
      <table class="mail-card" role="presentation" width="960" style="padding:24px">
        <tr><td><h1 class="mail-title">Предложение поставщика</h1><p>Готовы предложить решение.</p><button class="cta" type="button">Открыть предложение</button></td></tr>
      </table>
    `,
    status: 'received',
    error: null,
    message_id: '<html-reader-9302@example.com>',
    in_reply_to: null,
    references_header: null,
    created_at: '2026-08-30T08:00:00+00:00',
    sent_at: null,
    delivery_resolved: false,
    delivery_resolution: null,
    has_remote_images: false,
  };

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { items: [] };
    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'buyer@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/correspondence') {
      payload = { items: [thread] };
    } else if (url.pathname === '/api/mail/threads') {
      payload = { items: [message] };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/messages', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /ООО «Тестовый поставщик»/ }).click();
  const emailFrame = page.locator('iframe[title="Содержимое письма"]');
  await expect(emailFrame).toBeVisible();
  const metrics = await emailFrame.evaluate((element) => {
    const iframe = element as HTMLIFrameElement;
    const doc = iframe.contentDocument;
    const card = doc?.querySelector<HTMLElement>('.mail-card');
    const title = doc?.querySelector<HTMLElement>('.mail-title');
    const cta = doc?.querySelector<HTMLElement>('.cta');
    return {
      bodyText: doc?.body?.innerText ?? '',
      bodyClientWidth: doc?.documentElement.clientWidth ?? 0,
      bodyScrollWidth: doc?.documentElement.scrollWidth ?? 0,
      cardWidth: card?.getBoundingClientRect().width ?? 0,
      cardBackground: card ? getComputedStyle(card).backgroundColor : '',
      cardBorderRadius: card ? getComputedStyle(card).borderTopLeftRadius : '',
      titleColor: title ? getComputedStyle(title).color : '',
      ctaBackground: cta ? getComputedStyle(cta).backgroundColor : '',
      ctaText: cta?.textContent ?? '',
      styleBlocks: doc?.querySelectorAll('style').length ?? 0,
      scripts: doc?.querySelectorAll('script').length ?? 0,
    };
  });
  expect(metrics.bodyText).toContain('Готовы предложить решение');
  expect(metrics.styleBlocks).toBeGreaterThanOrEqual(2);
  expect(metrics.scripts).toBe(0);
  expect(metrics.cardBackground).toBe('rgb(238, 246, 255)');
  expect(metrics.cardBorderRadius).toBe('14px');
  expect(metrics.titleColor).toBe('rgb(18, 57, 91)');
  expect(metrics.ctaBackground).toBe('rgb(23, 105, 170)');
  expect(metrics.ctaText).toContain('Открыть предложение');
  expect(metrics.cardWidth).toBeLessThanOrEqual(metrics.bodyClientWidth + 1);
  expect(metrics.bodyScrollWidth).toBeLessThanOrEqual(metrics.bodyClientWidth + 1);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-matched-html-reader.png`), fullPage: false });

  await page.getByRole('button', { name: 'Ответить', exact: true }).first().click();
  const replyDialog = page.getByRole('dialog', { name: 'Ответить' });
  await expect(replyDialog).toBeVisible();
  await expect(replyDialog.getByRole('textbox', { name: 'Текст письма' })).toBeFocused();
  await expect(replyDialog.getByRole('button', { name: 'Закрыть форму ответа' })).toBeVisible();
  await replyDialog.getByRole('button', { name: 'Закрыть форму ответа' }).click();
  await expect(replyDialog).toBeHidden();

  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations, formatAxeViolations(axeResults.violations)).toEqual([]);
});

test('request error stays inside its request row and responsive layout does not overflow', async ({ page }, testInfo) => {
  const requestItems = [
    {
      id: 1051,
      name: 'Test web fallback API',
      description: null,
      deadline: '',
      sender_name: 'Снабжение',
      company_name: 'SupplyDesk',
      created_at: '2026-08-25T10:00:00+00:00',
      status: 'error',
      search_progress: 0,
      search_total: 1,
      search_depth: 1,
      last_error: 'Поиск прерван перезапуском сервера. Запустите поиск заново.',
      updated_at: '2026-08-25T10:01:00+00:00',
      positions_count: 1,
      suppliers_count: 74,
      sent_count: 0,
      replies_count: 0,
    },
    {
      id: 1058,
      name: 'Печь камин — длинное название для проверки устойчивости строки заявки',
      description: null,
      deadline: '',
      sender_name: 'Снабжение',
      company_name: 'SupplyDesk',
      created_at: '2026-08-27T20:34:57+00:00',
      status: 'searching',
      search_progress: 1,
      search_total: 1,
      search_depth: 1,
      last_error: null,
      updated_at: '2026-08-27T20:35:30+00:00',
      positions_count: 1,
      suppliers_count: 41,
      sent_count: 0,
      replies_count: 0,
    },
  ];

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = {
        authenticated: true,
        csrf_token: 'audit-token',
        user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
      };
    } else if (url.pathname === '/api/requests') {
      payload = { items: requestItems };
    } else if (url.pathname === '/api/dashboard/summary') {
      payload = {
        kpis: { active_requests: 1, searching_requests: 1, new_replies: 0, attention: 1, unmatched_mail: 0 },
        requests: requestItems,
      };
    } else if (url.pathname === '/api/enrichment/step') {
      payload = { ok: true, processed: false, status: 'idle' };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });

  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(geometry.scrollWidth, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.clientWidth + 1);

  const warning = page.getByRole('alert').filter({ hasText: 'Нужна проверка.' }).first();
  await expect(warning).toBeVisible();

  if ((testInfo.project.use.viewport?.width ?? 0) >= 1536) {
    const rowGeometry = await warning.evaluate((element) => {
      const row = element.closest('tr');
      const status = row?.querySelector('td:nth-child(2)');
      const warningRect = element.getBoundingClientRect();
      const rowRect = row?.getBoundingClientRect();
      const statusRect = status?.getBoundingClientRect();
      return {
        rowCount: element.closest('tbody')?.querySelectorAll('tr').length ?? 0,
        inSameRow: Boolean(row && status),
        warningCenter: warningRect.top + warningRect.height / 2,
        rowCenter: rowRect ? rowRect.top + rowRect.height / 2 : 0,
        statusCenter: statusRect ? statusRect.top + statusRect.height / 2 : 0,
      };
    });
    expect(rowGeometry.inSameRow).toBe(true);
    expect(rowGeometry.rowCount).toBe(requestItems.length);
    expect(Math.abs(rowGeometry.warningCenter - rowGeometry.rowCenter)).toBeLessThanOrEqual(2);
    expect(Math.abs(rowGeometry.warningCenter - rowGeometry.statusCenter)).toBeLessThanOrEqual(2);
  }

  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-requests-error-inline.png`),
    fullPage: true,
  });

  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations, formatAxeViolations(axeResults.violations)).toEqual([]);
});

test('long registry status stays inside its own table column', async ({ page }, testInfo) => {
  const longRegistryStatus = 'Юридическое лицо находится в процессе реорганизации в форме присоединения';
  const requestItem = {
    id: 1059,
    name: 'Печь-камин — глубокий поиск 20',
    description: null,
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-28T05:00:00+00:00',
    status: 'completed',
    search_progress: 1,
    search_total: 1,
    search_depth: 20,
    last_error: null,
    updated_at: '2026-08-28T05:01:00+00:00',
    positions_count: 1,
    suppliers_count: 1,
    sent_count: 0,
    replies_count: 0,
  };
  const supplier = {
    id: 9001,
    external_key: 'long-status.example',
    name: 'ООО «Длинный статус»',
    email: 'sales@long-status.example',
    host: 'long-status.example',
    inn: '7700000000',
    kind: 'company',
    region: 'Москва',
    role: '',
    phone: '',
    reason: 'Найдено по запросу',
    source: 'web',
    found_url: 'https://long-status.example',
    covers: [],
    position_keys: ['p1'],
    site_unavailable: 0,
    mail_status: 'not_sent',
    last_error: null,
    registry: {
      ogrn: '1234567890123',
      status: longRegistryStatus,
      is_active: false,
      registered_at: '2020-01-01T00:00:00+00:00',
    },
    finances: { report_year: 2025, revenue: 365600000, profit: 83700000 },
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  };

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = {
        authenticated: true,
        csrf_token: 'audit-token',
        user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
      };
    } else if (url.pathname === '/api/requests/1059') {
      payload = {
        request: requestItem,
        positions: [{ id: 1, request_id: 1059, position_key: 'p1', name: 'Печь-камин', quantity: '', created_at: requestItem.created_at }],
        items: [supplier],
      };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/1059', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
  await expectNoHorizontalOverflow(page);

  if (await page.locator('[data-supplier-column="mail-status"]').first().isVisible()) {
    const registry = page.locator(`[title="${longRegistryStatus} — статус в ЕГРЮЛ по данным Checko"]:visible`);
    await expect(registry).toBeVisible();
    await expect(registry).toContainText('Не действует');
    await expect(registry).toHaveAttribute('title', `${longRegistryStatus} — статус в ЕГРЮЛ по данным Checko`);
    await expect(registry).not.toContainText(longRegistryStatus);

    const geometry = await registry.evaluate((element) => {
      const cell = element.parentElement;
      const row = cell?.parentElement;
      const cellIndex = cell && row ? Array.from(row.children).indexOf(cell) : -1;
      const mail = cellIndex >= 0 ? row?.children[cellIndex + 1] : null;
      const checko = cellIndex >= 0 ? row?.children[cellIndex + 2] : null;
      const rect = (node: Element | null | undefined) => node?.getBoundingClientRect();
      const statusRect = element.getBoundingClientRect();
      const cellRect = cell?.getBoundingClientRect();
      const checkoRect = rect(checko);
      const mailRect = rect(mail);
      return {
        statusRight: statusRect.right,
        cellRight: cellRect?.right,
        checkoLeft: checkoRect?.left,
        mailLeft: mailRect?.left,
      };
    });
    expect(geometry.statusRight).toBeLessThanOrEqual((geometry.cellRight ?? 0) + 1);
    expect(geometry.statusRight).toBeLessThanOrEqual((geometry.checkoLeft ?? 0) - 1);
    expect(geometry.mailLeft).toBeLessThanOrEqual((geometry.checkoLeft ?? 0) - 1);
  }

  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-long-registry-status.png`),
    fullPage: true,
  });
});

test('arbitrary search depth and workspace mail template work without responsive overflow', async ({ page }, testInfo) => {
  let requestPayload: Record<string, unknown> | null = null;
  let savedTemplate: Record<string, unknown> | null = null;
  const requestItem = {
    id: 1060,
    name: 'Глубокий поиск кабельной продукции',
    description: null,
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-28T10:00:00+00:00',
    status: 'completed',
    search_progress: 1,
    search_total: 1,
    search_depth: 37,
    last_error: null,
    updated_at: '2026-08-28T10:01:00+00:00',
    positions_count: 1,
    suppliers_count: 0,
    sent_count: 0,
    replies_count: 0,
  };
  const baseTemplate = {
    subject: 'Запрос предложения — {{request_name}}',
    body: 'Добрый день, {{supplier_name}}!\n\nПросим направить предложение для {{company_name}}.',
    attachments: [],
    updated_at: null,
  };

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const status = 200;
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = {
        authenticated: true,
        csrf_token: 'audit-token',
        user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
      };
    } else if (url.pathname === '/api/dashboard/summary') {
      payload = {
        kpis: { active_requests: 0, searching_requests: 0, new_replies: 0, attention: 0, unmatched_mail: 0 },
        requests: [],
      };
    } else if (url.pathname === '/api/enrichment/step') {
      payload = { ok: true, processed: false, status: 'idle' };
    } else if (url.pathname === '/api/requests' && request.method() === 'POST') {
      requestPayload = request.postDataJSON() as Record<string, unknown>;
      payload = { ok: true, request_id: 1060 };
    } else if (url.pathname === '/api/requests/1060/search') {
      payload = { ok: true };
    } else if (url.pathname === '/api/requests/1060') {
      payload = {
        request: requestItem,
        positions: [{ id: 1, request_id: 1060, position_key: 'p1', name: 'Кабель ВВГ', quantity: '', created_at: requestItem.created_at }],
        items: [],
      };
    } else if (url.pathname === '/api/mail/status') {
      payload = { connected: true, provider: 'yandex', email: 'audit@yandex.ru', status: 'connected' };
    } else if (url.pathname === '/api/mail/template' && request.method() === 'POST') {
      savedTemplate = request.postDataJSON() as Record<string, unknown>;
      payload = { ok: true, ...savedTemplate, updated_at: '2026-08-28T10:05:00+00:00' };
    } else if (url.pathname === '/api/mail/template') {
      payload = baseTemplate;
    } else {
      status = 404;
      payload = { error: `Unhandled audit route: ${request.method()} ${url.pathname}` };
    }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/new', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
  await page.getByLabel('Название заявки').fill('Глубокий поиск кабельной продукции');
  await page.getByLabel('Глубина поиска').fill('37');
  await page.getByLabel('Позиция 1').fill('Кабель ВВГ');
  await page.getByRole('button', { name: 'Начать поиск поставщиков' }).click();

  const confirmation = page.getByRole('alert').filter({ hasText: 'Глубина 37' });
  await expect(confirmation).toContainText('до 37 страниц');
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-new-request-depth-37.png`),
    fullPage: true,
  });
  const newRequestAxe = await new AxeBuilder({ page }).analyze();
  expect(newRequestAxe.violations, formatAxeViolations(newRequestAxe.violations)).toEqual([]);

  await page.getByRole('button', { name: 'Подтвердить запуск' }).click();
  await expect(page).toHaveURL(/\/requests\/1060$/);
  expect(requestPayload).not.toBeNull();
  expect(requestPayload?.search_depth).toBe(37);

  await page.goto('/settings', { waitUntil: 'networkidle' });
  await page.getByLabel('Тема письма').fill('Запрос КП — {{request_name}}');
  await page.getByLabel('Текст письма').fill('Здравствуйте, {{supplier_name}}!\nНужна цена для {{company_name}}.');
  await page.getByLabel('Прикрепить файл к шаблону').setInputFiles({
    name: 'Техническое-задание.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 visual audit'),
  });
  await expect(page.getByText('Техническое-задание.pdf')).toBeVisible();
  await page.getByRole('button', { name: 'Сохранить шаблон' }).click();
  await expect(page.getByText('Шаблон сохранён')).toBeVisible();
  expect(savedTemplate).not.toBeNull();
  expect(savedTemplate?.subject).toBe('Запрос КП — {{request_name}}');
  expect((savedTemplate?.attachments as unknown[]).length).toBe(1);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-settings-mail-template.png`),
    fullPage: true,
  });
  const settingsAxe = await new AxeBuilder({ page }).analyze();
  expect(settingsAxe.violations, formatAxeViolations(settingsAxe.violations)).toEqual([]);
});

test('supplier card keeps long content readable and exposes manual inn and blacklist actions', async ({ page }, testInfo) => {
  let innPayload: Record<string, unknown> | null = null;
  let blacklistPayload: Record<string, unknown> | null = null;
  const requestItem = {
    id: 1059,
    name: 'Печь-камин — карточка поставщика',
    description: null,
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-28T10:00:00+00:00',
    status: 'completed',
    search_progress: 1,
    search_total: 1,
    search_depth: 20,
    last_error: null,
    updated_at: '2026-08-28T10:01:00+00:00',
    positions_count: 1,
    suppliers_count: 1,
    sent_count: 0,
    replies_count: 0,
  };
  const supplier = {
    id: 9002,
    external_key: 'very-long-supplier.example',
    name: 'ООО «Поставщик с очень длинным названием для проверки переноса текста»',
    email: 'sales-with-a-very-long-local-part@very-long-supplier.example',
    host: 'very-long-supplier.example',
    inn: '',
    inn_source: '',
    kind: 'company',
    region: 'Санкт-Петербург',
    role: 'производитель',
    phone: '+7 999 123-45-67',
    reason: 'Найдено по ключу печь камин и совпадению с карточкой поставщика без сокращения текста',
    source: 'web',
    found_url: 'https://very-long-supplier.example/catalog/pechi-kaminy',
    covers: [],
    position_keys: ['p1'],
    site_unavailable: 0,
    mail_status: 'not_sent',
    last_error: null,
    registry: {
      ogrn: '1027700132195',
      status: 'Юридическое лицо находится в процессе реорганизации в форме присоединения',
      is_active: true,
      registered_at: '2020-01-01T00:00:00+00:00',
    },
    finances: { report_year: 2025, revenue: 365600000, profit: 83700000 },
    global_supplier_id: null,
    risks: ['Юридическое лицо находится в процессе реорганизации'],
    unread_count: 0,
  };

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = {
        authenticated: true,
        csrf_token: 'audit-token',
        user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
      };
    } else if (url.pathname === '/api/requests/1059') {
      payload = {
        request: requestItem,
        positions: [{ id: 1, request_id: 1059, position_key: 'p1', name: 'Печь-камин', quantity: '', created_at: requestItem.created_at }],
        items: [supplier],
      };
    } else if (url.pathname.endsWith('/suppliers/9002/inn') && request.method() === 'POST') {
      innPayload = request.postDataJSON() as Record<string, unknown>;
      supplier.inn = String(innPayload.inn || '');
      supplier.inn_source = 'manual';
      payload = { ok: true, inn: supplier.inn, inn_source: 'manual', checko_status: 'loaded', checko_error: '', global_supplier_id: 9002 };
    } else if (url.pathname === '/api/blacklist' && request.method() === 'POST') {
      blacklistPayload = request.postDataJSON() as Record<string, unknown>;
      payload = { ok: true, entry_id: 11 };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/1059', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
  const isDesktopTable = await page.locator('[data-supplier-column="mail-status"]').first().isVisible();
  const visibleRow = (isDesktopTable
    ? page.locator('div[class*="group/row"]')
    : page.locator('article')
  ).filter({ hasText: 'very-long-supplier.example' }).first();

  if (!isDesktopTable) {
    const workflowBounds = await page.locator('[data-workflow-step]').evaluateAll((nodes) =>
      nodes.map((node) => {
        const rect = node.getBoundingClientRect();
        return { left: rect.left, right: rect.right, viewport: window.innerWidth };
      }),
    );
    expect(workflowBounds).toHaveLength(5);
    expect(workflowBounds.every(({ left, right, viewport }) => left >= -1 && right <= viewport + 1)).toBeTruthy();

    const searchBounds = await page.getByPlaceholder('Поиск компании, ИНН, сайта…').evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, viewport: window.innerWidth };
    });
    expect(searchBounds.left).toBeGreaterThanOrEqual(-1);
    expect(searchBounds.right).toBeLessThanOrEqual(searchBounds.viewport + 1);

    const title = visibleRow.getByTitle(supplier.name);
    await expect(title).toHaveText(supplier.name);
    await expect(title).not.toHaveCSS('text-overflow', 'ellipsis');
    await expect(visibleRow.getByTitle(supplier.email)).toHaveText(supplier.email);
  }

  // A viewport capture represents what a person can actually see. Full-page
  // screenshots compose fixed/sticky navigation at an arbitrary scroll
  // position and can fabricate a visual overlap that the live page does not
  // have. Capture the stressed card itself before opening the detail panel.
  await visibleRow.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-supplier-card-long-content.png`),
    fullPage: false,
  });

  await visibleRow.getByRole('button', { name: /Открыть/ }).click();
  const panel = page.locator('aside.shadow-panel');
  await expect(panel.getByRole('heading')).toContainText('Поставщик с очень длинным названием');
  await expect(panel.getByText('Действует', { exact: true })).toBeVisible();
  await expect(panel.getByText('Внесён пользователем', { exact: true })).toHaveCount(0);

  await panel.locator('#supplier-inn').fill('7707083893');
  await panel.getByRole('button', { name: 'Сохранить' }).click();
  await expect(panel.getByText('ИНН сохранён, данные Checko обновлены.')).toBeVisible();
  expect(innPayload?.inn).toBe('7707083893');
  await expect(panel.getByText('Внесён пользователем', { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-supplier-panel-manual-inn-open.png`),
    fullPage: false,
  });
  const panelAxe = await new AxeBuilder({ page }).include('aside.shadow-panel').analyze();
  expect(panelAxe.violations, formatAxeViolations(panelAxe.violations)).toEqual([]);

  await panel.getByRole('button', { name: 'В чёрный список' }).click();
  await panel.locator('#request-blacklist-reason').fill('Тест визуального сценария');
  await panel.getByRole('button', { name: 'Добавить в ЧС' }).click();
  expect(blacklistPayload?.external_key).toBe('very-long-supplier.example');
  expect(blacklistPayload?.reason).toBe('Тест визуального сценария');
  await expect(panel).toBeHidden();

  await expectNoHorizontalOverflow(page);
  await visibleRow.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-supplier-panel-manual-inn.png`),
    fullPage: false,
  });
});

test('messages default list keeps sent and replied mail separate from the outbox', async ({ page }, testInfo) => {
  const thread = (overrides: Record<string, unknown>) => ({
    request_id: 2001,
    supplier_id: 2001,
    subject: 'Запрос коммерческого предложения',
    last_message_at: '2026-08-29T10:00:00+00:00',
    created_at: '2026-08-29T09:00:00+00:00',
    request_name: 'Проверка списка переписки',
    supplier_name: 'Поставщик без статуса',
    supplier_email: 'sales@example.com',
    supplier_host: 'example.com',
    supplier_external_key: 'example.com',
    messages_count: 1,
    replies_count: 0,
    unread_count: 0,
    pending_outbound_count: 0,
    last_outbound_status: 'sent',
    last_message_direction: 'outbound',
    ...overrides,
  });
  const sentThread = thread({ supplier_id: 2001, supplier_name: 'Отправленный поставщик' });
  const repliedThread = thread({
    supplier_id: 2002,
    supplier_name: 'Ответивший поставщик',
    replies_count: 1,
    unread_count: 1,
    last_message_direction: 'inbound',
  });
  const queuedThread = thread({
    request_id: 2002,
    supplier_id: 2003,
    request_name: 'Письмо только в очереди',
    supplier_name: 'Ожидающий поставщик',
    supplier_email: 'queue@example.com',
    supplier_host: 'queue.example.com',
    supplier_external_key: 'queue.example.com',
    last_outbound_status: 'queued',
    pending_outbound_count: 1,
  });
  const failedThread = thread({
    request_id: 2003,
    supplier_id: 2004,
    request_name: 'Письмо с ошибкой',
    supplier_name: 'Поставщик с ошибкой',
    supplier_email: 'failed@example.com',
    supplier_host: 'failed.example.com',
    supplier_external_key: 'failed.example.com',
    last_outbound_status: 'failed',
  });
  const unknownThread = thread({
    request_id: 2004,
    supplier_id: 2005,
    request_name: 'Письмо с неопределённым статусом',
    supplier_name: 'Поставщик без подтверждения',
    supplier_email: 'unknown@example.com',
    supplier_host: 'unknown.example.com',
    supplier_external_key: 'unknown.example.com',
    last_outbound_status: 'delivery_unknown',
  });

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/correspondence') {
      payload = { items: [sentThread, repliedThread, queuedThread, failedThread, unknownThread] };
    } else if (url.pathname === '/api/mail/queue/messages') {
      payload = { items: [queuedThread] };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/messages', { waitUntil: 'networkidle' });
  await expect(page.getByRole('button', { name: /Отправленные и ответы/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: /Отправленный поставщик/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ответивший поставщик/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ожидающий поставщик/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Поставщик с ошибкой/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Поставщик без подтверждения/ })).toHaveCount(0);

  await page.getByRole('button', { name: 'Очередь', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Очередь отправки' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ожидающий поставщик/ })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-messages-primary-and-outbox.png`), fullPage: false });
});

test('delivery unknown stays actionable when opened directly from the supplier row', async ({ page }, testInfo) => {
  const requestItem = {
    id: 1070,
    name: 'Проверка неопределённой отправки',
    description: 'Тестовая заявка для проверки безопасного статуса отправки.',
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
    suppliers_count: 1,
    sent_count: 0,
    replies_count: 0,
  };
  const supplier = {
    id: 9070,
    external_key: 'uncertain.example',
    name: 'ООО «Надёжный поставщик»',
    email: 'sales@uncertain.example',
    host: 'uncertain.example',
    inn: '7700000000',
    kind: 'company',
    region: 'Москва',
    role: 'производитель',
    phone: '+7 495 000-00-00',
    reason: 'Найдено по заявке',
    source: 'web',
    found_url: 'https://uncertain.example',
    covers: ['p1'],
    position_keys: ['p1'],
    site_unavailable: 0,
    mail_status: 'delivery_unknown',
    delivery_issue_resolved: false,
    last_error: 'Соединение оборвалось после начала передачи письма.',
    registry: null,
    finances: null,
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  };
  const thread = {
    id: 9071,
    request_id: 1070,
    supplier_id: 9070,
    subject: 'Запрос коммерческого предложения',
    last_message_at: '2026-08-28T10:02:00+00:00',
    created_at: '2026-08-28T10:00:00+00:00',
    request_name: requestItem.name,
    supplier_name: supplier.name,
    supplier_email: supplier.email,
    supplier_host: supplier.host,
    supplier_external_key: supplier.external_key,
    messages_count: 1,
    replies_count: 0,
    unread_count: 0,
    pending_outbound_count: 0,
    last_outbound_status: 'delivery_unknown',
    last_message_direction: 'outbound',
  };
  const message = {
    id: 9072,
    direction: 'outbound',
    from_email: 'buyer@example.com',
    to_email: supplier.email,
    subject: thread.subject,
    body_text: 'Пожалуйста, направьте коммерческое предложение.',
    body_html: '<p>Пожалуйста, направьте коммерческое предложение.</p>',
    status: 'delivery_unknown',
    error: 'Соединение оборвалось после начала передачи письма.',
    message_id: '<integrity-9072@example.com>',
    in_reply_to: null,
    references_header: null,
    created_at: '2026-08-28T10:02:00+00:00',
    sent_at: null,
    delivery_resolved: false,
    delivery_resolution: null,
  };

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const status = 200;
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/requests/1070') {
      payload = { request: requestItem, positions: [{ id: 1, request_id: 1070, position_key: 'p1', name: 'Насос', quantity: '1', created_at: requestItem.created_at }], items: [supplier] };
    } else if (url.pathname === '/api/correspondence') {
      payload = { items: [thread] };
    } else if (url.pathname === '/api/mail/threads') {
      payload = { items: [message] };
    } else if (/^\/api\/mail\/messages\/9072\/verify$/.test(url.pathname)) {
      payload = { outcome: 'not_found', status: 'delivery_unknown', message_id: 9072 };
    } else if (/^\/api\/mail\/messages\/9072\/resend$/.test(url.pathname)) {
      payload = { ok: true, resent: false, requires_confirmation: true, warning: 'Оригинал не подтверждён. Повтор может создать дубликат.' };
    } else if (/^\/api\/mail\/messages\/9072\/resolve$/.test(url.pathname)) {
      payload = { ok: true, already_resolved: false, resolved_at: '2026-08-28T10:03:00+00:00' };
    }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/1070', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });
  await expect(page.locator('span:visible').filter({ hasText: 'Статус неизвестен' }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-delivery-unknown-row.png`), fullPage: true });

  await page.goto('/messages', { waitUntil: 'networkidle' });
  await expect(page.getByRole('button', { name: /ООО «Надёжный поставщик»/ })).toHaveCount(0);
  await page.goto('/messages?thread=1070:9070', { waitUntil: 'networkidle' });
  await expect(page.getByRole('alert')).toContainText('Оно не будет отправлено повторно автоматически');
  await expect(page.getByRole('button', { name: 'Проверить ещё раз' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Отправить повторно' })).toBeVisible();
  await page.getByRole('button', { name: 'Отправить повторно' }).click();
  await expect(page.getByRole('button', { name: 'Подтвердить повтор' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-delivery-unknown-thread.png`), fullPage: true });
  const axeResults = await new AxeBuilder({ page }).analyze();
  expect(axeResults.violations, formatAxeViolations(axeResults.violations)).toEqual([]);
});

test('outbound workflow is coherent and the supplier mail status stays separate from Checko', async ({ page }, testInfo) => {
  const requestItem = {
    id: 1080,
    name: 'Проверка статуса исходящего запроса',
    description: 'Письмо принято почтовым сервером, но ответ ещё не получен.',
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-28T12:00:00+00:00',
    status: 'draft',
    search_progress: 0,
    search_total: 1,
    search_depth: 1,
    last_error: null,
    updated_at: '2026-08-28T12:01:00+00:00',
    positions_count: 1,
    suppliers_count: 1,
    sent_count: 0,
    replies_count: 0,
    mail_metrics: {
      outbound_total: 1,
      queued: 0,
      accepted: 1,
      accepted_effective: 1,
      failed: 0,
      delivery_unknown: 0,
      bounced: 0,
      cancelled: 0,
      replies: 0,
    },
  };
  const supplier = {
    id: 9080,
    external_key: 'status-check.example',
    name: 'ООО «Поставщик со статусом письма»',
    email: 'sales@status-check.example',
    host: 'status-check.example',
    inn: '7700000000',
    kind: 'company',
    region: 'Москва',
    role: 'производитель',
    phone: '+7 495 000-00-00',
    reason: 'Найден по релевантному запросу',
    source: 'web',
    found_url: 'https://status-check.example',
    covers: ['p1'],
    position_keys: ['p1'],
    site_unavailable: 0,
    // `waiting` — это communication state поверх SMTP acceptance; доставка
    // во входящие этим статусом не подтверждается.
    mail_status: 'waiting',
    last_error: null,
    registry: null,
    finances: null,
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  };

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = {
        authenticated: true,
        csrf_token: 'audit-token',
        user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' },
      };
    } else if (url.pathname === '/api/requests/1080') {
      payload = {
        request: requestItem,
        positions: [{ id: 1, request_id: 1080, position_key: 'p1', name: 'Печь-камин', quantity: '1', created_at: requestItem.created_at }],
        items: [supplier],
      };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/1080', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });

  // `role` may remain an internal enrichment field, but it is no longer a
  // user-facing supplier concept. A stale API field must not recreate a filter
  // or a badge after the product has retired that concept.
  await expect(page.getByText('Производители', { exact: true })).toHaveCount(0);
  await expect(page.getByText('производитель', { exact: true })).toHaveCount(0);

  // An accepted SMTP message cannot coexist with the user-facing
  // "Черновик / 0 принято почтовым сервером" state.
  await expect(page.getByText('В работе', { exact: true })).toBeVisible();
  await expect(page.getByText('1 отправлено', { exact: true })).toBeVisible();
  await expect(page.locator('span:visible').filter({ hasText: /^◷\s*Ждём ответа$/ }).first()).toBeVisible();
  await expect(page.getByText('Черновик', { exact: true })).toHaveCount(0);

  const toolbar = page.locator('[data-supplier-toolbar]');
  await expect(toolbar).toBeVisible();
  const background = await page.evaluate(() => {
    const toolbarNode = document.querySelector<HTMLElement>('[data-supplier-toolbar]');
    const pageNode = toolbarNode?.closest('main')?.parentElement;
    return {
      toolbar: toolbarNode ? getComputedStyle(toolbarNode).backgroundColor : null,
      page: pageNode ? getComputedStyle(pageNode).backgroundColor : null,
    };
  });
  expect(background).toEqual({ toolbar: 'rgb(248, 250, 252)', page: 'rgb(248, 250, 252)' });

  if (await page.locator('[data-supplier-column="mail-status"]').first().isVisible()) {
    const geometry = await page.evaluate(() => {
      const rectangle = (selector: string, index: number) => {
        const element = document.querySelectorAll<HTMLElement>(selector)[index];
        if (!element) return null;
        const { left, right, width } = element.getBoundingClientRect();
        return { left, right, width };
      };
      return {
        mailHeader: rectangle('[data-supplier-column="mail-status"]', 0),
        checkoHeader: rectangle('[data-supplier-column="checko"]', 0),
        mailCell: rectangle('[data-supplier-column="mail-status"]', 1),
        checkoCell: rectangle('[data-supplier-column="checko"]', 1),
      };
    });
    expect(geometry.mailHeader).not.toBeNull();
    expect(geometry.checkoHeader).not.toBeNull();
    expect(geometry.mailCell).not.toBeNull();
    expect(geometry.checkoCell).not.toBeNull();
    expect(geometry.mailHeader!.right).toBeLessThan(geometry.checkoHeader!.left);
    expect(geometry.mailCell!.right).toBeLessThan(geometry.checkoCell!.left);
    expect(geometry.mailHeader!.width).toBeGreaterThan(150);
    expect(geometry.checkoHeader!.width).toBeGreaterThanOrEqual(70);
  }

  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath(`${testInfo.project.name}-supplier-status-and-checko.png`),
    fullPage: false,
  });
});

test('request status vocabulary separates message metrics from company filters', async ({ page }, testInfo) => {
  const requestItem = {
    id: 1090,
    name: 'Проверка понятных статусов письма',
    description: null,
    deadline: '',
    sender_name: 'Снабжение',
    company_name: 'SupplyDesk',
    created_at: '2026-08-30T10:00:00+00:00',
    status: 'completed',
    search_progress: 1,
    search_total: 1,
    search_depth: 1,
    last_error: null,
    updated_at: '2026-08-30T10:01:00+00:00',
    positions_count: 1,
    suppliers_count: 6,
    sent_count: 2,
    replies_count: 1,
    mail_metrics: {
      outbound_total: 131,
      queued: 84,
      accepted: 45,
      accepted_effective: 44,
      failed: 2,
      delivery_unknown: 0,
      bounced: 1,
      cancelled: 0,
      replies: 1,
    },
  };
  const baseSupplier = {
    external_key: 'status-vocabulary.example',
    name: 'ООО «Компания со статусом»',
    host: 'status-vocabulary.example',
    inn: '7700000000',
    kind: 'company',
    region: 'Москва',
    role: 'поставщик',
    phone: '+7 495 000-00-00',
    reason: 'Тестовая карточка',
    source: 'web',
    found_url: 'https://status-vocabulary.example',
    covers: ['p1'],
    position_keys: ['p1'],
    site_unavailable: 0,
    registry: null,
    finances: null,
    global_supplier_id: null,
    risks: null,
    unread_count: 0,
  };
  const supplier = (id: number, email: string, delivery_counts: Record<string, number>, extra: Record<string, unknown> = {}) => ({
    ...baseSupplier,
    id,
    email,
    email_count: 1,
    delivery_counts: { not_sent: 0, queued: 0, accepted: 0, failed: 0, delivery_unknown: 0, bounced: 0, cancelled: 0, ...delivery_counts },
    mail_status: 'sent',
    last_error: null,
    ...extra,
  });
  const suppliers = [
    supplier(10901, 'new@status-vocabulary.example', { not_sent: 1 }, { mail_status: 'not_sent' }),
    supplier(10902, 'queued@status-vocabulary.example', { queued: 1 }),
    supplier(10903, 'accepted@status-vocabulary.example', { accepted: 1 }, { mail_status: 'waiting', response_status: 'waiting' }),
    supplier(10904, 'failed@status-vocabulary.example', { failed: 1 }, { mail_status: 'error', last_error: 'Провайдер отклонил письмо по политике отправки.' }),
    supplier(10905, 'bounced@status-vocabulary.example', { bounced: 1 }, { mail_status: 'error' }),
    supplier(10906, 'mixed-0@status-vocabulary.example', { queued: 1, accepted: 3 }, {
      email_count: 4,
      site_count: 4,
      mail_status: 'waiting',
      response_status: 'waiting',
      contacts: [
        { supplier_id: 10906, email: 'mixed-0@status-vocabulary.example', host: 'status-0.example', mail_status: 'waiting', delivery_status: 'accepted', response_status: 'waiting' },
        { supplier_id: 10907, email: 'mixed-1@status-vocabulary.example', host: 'status-1.example', mail_status: 'waiting', delivery_status: 'accepted', response_status: 'waiting' },
        { supplier_id: 10908, email: 'mixed-2@status-vocabulary.example', host: 'status-2.example', mail_status: 'waiting', delivery_status: 'accepted', response_status: 'waiting' },
        { supplier_id: 10909, email: 'mixed-3@status-vocabulary.example', host: 'status-3.example', mail_status: 'sent', delivery_status: 'queued', response_status: 'none' },
      ],
    }),
  ];

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    let payload: unknown = { ok: true };
    if (url.pathname === '/api/auth/me') {
      payload = { authenticated: true, csrf_token: 'audit-token', user: { email: 'audit@example.com', display_name: 'Аудит', workspace_name: 'SupplyDesk' } };
    } else if (url.pathname === '/api/requests/1090') {
      payload = {
        request: requestItem,
        positions: [{ id: 1, request_id: 1090, position_key: 'p1', name: 'Печь-камин', quantity: '1', created_at: requestItem.created_at }],
        items: suppliers,
      };
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });

  await page.goto('/requests/1090', { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '*, *::before, *::after { animation: none !important; transition: none !important; }' });

  const visibleText = await page.locator('body').innerText();
  expect(visibleText).toContain('Отправлено');
  expect(visibleText).not.toContain('Bounce');
  await expect(page.getByText('Письма:', { exact: true })).toBeVisible();
  await expect(page.getByText('Компании', { exact: true })).toBeVisible();
  await expect(page.getByText('44 отправлено', { exact: true })).toBeVisible();
  await expect(page.getByText('125 отправлено', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Ещё не отправляли\s+1/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ожидает отправки\s+2/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Отправлено\s+2/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ошибка отправки\s+1/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Не доставлено\s+1/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Ждём ответа\s+2/ })).toBeVisible();
  await expect(page.locator('span:visible').filter({ hasText: /^◷Ждём ответа· 3 контакта$/ }).first()).toBeVisible();
  await expect(page.locator('span:visible').filter({ hasText: /^◷Ожидает отправки· 1 контакт$/ }).first()).toBeVisible();
  await expect(page.locator('span:visible').filter({ hasText: /^↗Отправлено· 3 контакта$/ }).first()).toBeVisible();
  await expect(page.locator(`[title="Почтовый сервер принял письмо. Доставка во входящие не гарантируется."]:visible`).first()).toBeVisible();
  await expect(page.locator('span:visible').filter({ hasText: 'Почтовый сервер отклонил письмо как нежелательное' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Статус неизвестен/ })).toHaveCount(0);

  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-request-status-vocabulary.png`), fullPage: true });
});
