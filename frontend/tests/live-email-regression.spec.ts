import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

const projectRoot = path.resolve(process.cwd(), '..');
const artifactRoot = path.join(projectRoot, 'Temp', 'live-browser-email-20260830', 'after');
fs.mkdirSync(artifactRoot, { recursive: true });

const envText = fs.readFileSync(path.join(projectRoot, '.env'), 'utf8');
const readEnv = (key: string) => {
  const line = envText.split(/\r?\n/).find((item) => item.trim().startsWith(`${key}=`));
  return line ? line.slice(line.indexOf('=') + 1).trim().replace(/^['"]|['"]$/g, '') : '';
};

const viewports = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'desktop-1640', width: 1640, height: 900 },
  { name: 'tablet-1024', width: 1024, height: 768 },
  { name: 'mobile-390', width: 390, height: 844 },
];

const unmatchedCases = [
  { key: 'tariff', subject: 'Пара кликов до вашего тарифа' },
  { key: 'first-mail', subject: 'Первое письмо на почте' },
  { key: 'other-external', subject: 'Освободите память iPhone' },
  { key: 'no-images', subject: 'Печь.ру — ваше обращение принято' },
];

type SourceMessage = {
  id: number;
  subject: string;
  body_html: string | null;
  body_text: string | null;
  has_remote_images?: boolean;
};

function sourceStats(message: SourceMessage) {
  const html = message.body_html ?? '';
  return {
    id: message.id,
    htmlLength: html.length,
    textLength: (message.body_text ?? '').length,
    tables: (html.match(/<table\b/gi) ?? []).length,
    rows: (html.match(/<tr\b/gi) ?? []).length,
    cells: (html.match(/<td\b/gi) ?? []).length,
    externalImages: (html.match(/<img\b[^>]*(?:^|\s)src\s*=\s*["']https?:/gi) ?? []).length,
    blockedRemoteImages: (html.match(/<img\b[^>]*\bdata-remote-src\s*=/gi) ?? []).length,
    cidImages: (html.match(/<img\b[^>]*\bsrc\s*=\s*["']data:image\//gi) ?? []).length,
    externalBackgrounds: (html.match(/(?:background-image|background)\s*:\s*[^;]*url\(\s*["']?https?:/gi) ?? []).length,
    blockedBackgroundMarkers: (html.match(/data-remote-background=/gi) ?? []).length,
    blockedBodyBackgroundMarker: html.includes('data-remote-body-background='),
  };
}

async function loginThroughLiveApi(page: Page) {
  const response = await page.request.post('/api/auth/login', {
    data: { email: readEnv('APP_USER_EMAIL'), password: readEnv('APP_USER_PASSWORD') },
  });
  expect(response.status()).toBe(200);
  const me = await page.request.get('/api/auth/me');
  expect(me.status()).toBe(200);
  expect((await me.json()).authenticated).toBe(true);
}

async function openUnmatched(page: Page, subject: string) {
  await page.goto('/messages', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Без привязки', exact: true }).click();
  const search = page.getByLabel('Поиск писем без привязки');
  await expect(search).toBeVisible();
  await search.fill(subject);
  await page.waitForTimeout(450);
  const row = page.locator('button').filter({ hasText: subject }).last();
  await expect(row).toBeVisible();
  await row.click();
  const frames = page.locator('iframe[title="Содержимое письма"]');
  await expect(frames.first()).toBeVisible();
  await page.waitForTimeout(300);
  return frames;
}

async function openPlainThread(page: Page) {
  await page.goto('/messages', { waitUntil: 'networkidle' });
  const search = page.getByPlaceholder('Поиск по поставщику, заявке или письму...');
  await expect(search).toBeVisible();
  await search.fill('Запрос коммерческого предложения');
  await page.waitForTimeout(450);
  const row = page.locator('button').filter({ hasText: 'Запрос коммерческого предложения' }).last();
  await expect(row).toBeVisible();
  await row.click();
  const frames = page.locator('iframe[title="Содержимое письма"]');
  await expect(frames.first()).toBeVisible();
  await page.waitForTimeout(300);
  return frames;
}

async function openThread(page: Page, requestId: number, supplierId: number) {
  await page.goto(`/messages?thread=${requestId}:${supplierId}`, { waitUntil: 'networkidle' });
  const frames = page.locator('iframe[title="Содержимое письма"]');
  await expect(frames.first()).toBeVisible();
  await page.waitForTimeout(300);
  return frames;
}

async function assertRemoteImagesNotice(page: Page, expected: boolean) {
  const notice = page.getByTestId('email-remote-images-notice');
  if (expected) {
    await expect(notice).toHaveCount(1);
    await expect(notice).toContainText('Изображения отключены');
    await expect(notice).toContainText('Мы не загружаем картинки с внешних сайтов, чтобы защитить вашу конфиденциальность. Текст письма доступен');
    const iframe = page.locator('iframe[title="Содержимое письма"]').first();
    const iframeBox = await iframe.boundingBox();
    const noticeBox = await notice.boundingBox();
    expect(iframeBox).not.toBeNull();
    expect(noticeBox).not.toBeNull();
    expect(noticeBox!.y).toBeGreaterThanOrEqual(iframeBox!.y + iframeBox!.height);
  } else {
    await expect(notice).toHaveCount(0);
  }
}

async function frameMetrics(frame: ReturnType<Page['locator']>) {
  return frame.evaluate((element) => {
    const iframe = element as HTMLIFrameElement;
    const doc = iframe.contentDocument;
    const body = doc?.body;
    if (!doc || !body) return { error: 'renderer document unavailable' };

    const visible = (node: Element) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
        && rect.width > 0 && rect.height > 0;
    };
    const hasText = (node: Element) => Boolean((node.textContent ?? '').replace(/(?:\s|\u200b|\u200c|\u200d|\u2060|\ufeff)+/g, '').trim());
    const transparent = (color: string) => color === 'rgba(0, 0, 0, 0)' || color === 'transparent';
    const elements = [...body.querySelectorAll('*')];
    const textNodes = elements.filter((node) => hasText(node) && visible(node));
    const emptySpaceCandidates = elements
      .filter((node) => ['DIV', 'P', 'TD', 'TR', 'TABLE', 'IMG'].includes(node.tagName) && !hasText(node) && visible(node))
      .map((node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return {
          tag: node.tagName.toLowerCase(),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          style: node.getAttribute('style'),
          padding: style.padding,
          margin: style.margin,
        };
      })
      .filter((item) => item.height >= 80)
      .sort((left, right) => right.height - left.height)
      .slice(0, 20);
    const hidden = elements.filter((node) => {
      const style = getComputedStyle(node);
      return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
    }).length;
    const textStyles = textNodes.slice(0, 24).map((node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      let ancestor: Element | null = node;
      let background = style.backgroundColor;
      while (ancestor && transparent(background)) {
        ancestor = ancestor.parentElement;
        if (ancestor) background = getComputedStyle(ancestor).backgroundColor;
      }
      return {
        tag: node.tagName.toLowerCase(),
        text: (node.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 120),
        color: style.color,
        background,
        opacity: style.opacity,
        visibility: style.visibility,
        padding: style.padding,
        margin: style.margin,
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    });
    const images = [...doc.images].map((image) => ({
      src: (image.getAttribute('src') ?? '').slice(0, 120),
      blocked: image.hasAttribute('data-remote-src'),
      complete: image.complete,
      naturalWidth: image.naturalWidth,
      naturalHeight: image.naturalHeight,
      width: Math.round(image.getBoundingClientRect().width),
      height: Math.round(image.getBoundingClientRect().height),
    }));
    const overflowing = elements
      .filter((node) => hasText(node) && visible(node))
      .map((node) => ({ node, rect: node.getBoundingClientRect() }))
      .filter(({ rect }) => rect.left < -1 || rect.right > doc.documentElement.clientWidth + 1)
      .slice(0, 20)
      .map(({ node, rect }) => ({
        tag: node.tagName.toLowerCase(),
        text: (node.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 80),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      }));
    const lightTextOnTransparent = textStyles.filter((item) => item.color === 'rgb(255, 255, 255)' && transparent(item.background)).length;
    const explicitHiddenText = textStyles.filter((item) => item.opacity === '0' || item.visibility === 'hidden').length;
    const blockedBackgrounds = doc.querySelectorAll('[data-blocked-background]').length;

    return {
      iframe: {
        width: Math.round(iframe.getBoundingClientRect().width),
        height: Math.round(iframe.getBoundingClientRect().height),
      },
      document: {
        clientWidth: doc.documentElement.clientWidth,
        scrollWidth: doc.documentElement.scrollWidth,
        clientHeight: doc.documentElement.clientHeight,
        scrollHeight: doc.documentElement.scrollHeight,
      },
      body: {
        clientWidth: body.clientWidth,
        scrollWidth: body.scrollWidth,
        clientHeight: body.clientHeight,
        scrollHeight: body.scrollHeight,
        textLength: (body.innerText ?? '').trim().length,
        textSample: (body.innerText ?? '').replace(/\s+/g, ' ').trim().slice(0, 260),
      },
      finalHtml: {
        htmlLength: doc.documentElement.outerHTML.length,
        bodyHtmlLength: body.innerHTML.length,
        scripts: doc.scripts.length,
      },
      tables: { table: doc.querySelectorAll('table').length, tr: doc.querySelectorAll('tr').length, td: doc.querySelectorAll('td').length },
      styleBlocks: doc.querySelectorAll('style').length,
      visibleTextCount: textNodes.length,
      hiddenElements: hidden,
      transparentTextCount: lightTextOnTransparent + explicitHiddenText,
      emptySpaceCandidates,
      maxEmptySpaceHeight: emptySpaceCandidates[0]?.height ?? 0,
      textStyles,
      images,
      blockedImages: doc.querySelectorAll('img[data-remote-src]').length,
      blockedBackgrounds,
      backgroundImages: elements.filter((node) => getComputedStyle(node).backgroundImage !== 'none').length,
      overflowing,
      horizontalOverflow: doc.documentElement.scrollWidth > doc.documentElement.clientWidth + 1,
    };
  });
}

async function findScrollContainer(frame: ReturnType<Page['locator']>) {
  return frame.evaluate((element) => {
    let current = element.parentElement;
    while (current) {
      const style = getComputedStyle(current);
      if (current.scrollHeight > current.clientHeight + 1 && (style.overflowY === 'auto' || style.overflowY === 'scroll')) {
        return { clientHeight: current.clientHeight, scrollHeight: current.scrollHeight, scrollTop: current.scrollTop };
      }
      current = current.parentElement;
    }
    return null;
  });
}

async function setScrollPosition(page: Page, frame: ReturnType<Page['locator']>, position: 'top' | 'bottom') {
  await frame.evaluate((element, requestedPosition) => {
    let current = element.parentElement;
    while (current) {
      const style = getComputedStyle(current);
      if (current.scrollHeight > current.clientHeight + 1 && (style.overflowY === 'auto' || style.overflowY === 'scroll')) {
        current.scrollTop = requestedPosition === 'bottom' ? current.scrollHeight : 0;
        return;
      }
      current = current.parentElement;
    }
  }, position);
  await page.waitForTimeout(180);
}

async function captureCase(page: Page, frames: ReturnType<Page['locator']>, caseKey: string, viewportName: string, source: SourceMessage[], expectedNotice: boolean) {
  const safePrefix = `${caseKey}-${viewportName}`;
  const firstFrame = frames.first();
  const metrics = [];
  for (let index = 0; index < await frames.count(); index += 1) {
    metrics.push(await frameMetrics(frames.nth(index)));
  }
  const scrollBefore = await findScrollContainer(firstFrame);
  await assertRemoteImagesNotice(page, expectedNotice);
  expect(metrics.some((item) => 'body' in item && item.body.textLength > 20), `${caseKey} must contain visible text`).toBe(true);
  for (const item of metrics) {
    if ('document' in item) {
      expect(item.document.scrollWidth, JSON.stringify(item)).toBeLessThanOrEqual(item.document.clientWidth + 1);
      expect(item.horizontalOverflow, JSON.stringify(item)).toBe(false);
      expect(item.overflowing, JSON.stringify(item)).toEqual([]);
      expect(item.transparentTextCount, JSON.stringify(item)).toBe(0);
      expect(item.maxEmptySpaceHeight, JSON.stringify(item)).toBeLessThan(400);
      // Short plain-text mail must keep its real content height; the renderer
      // no longer adds the former 80px artificial minimum.
      expect(item.iframe.height).toBeGreaterThan(24);
    }
  }

  await setScrollPosition(page, firstFrame, 'top');
  await page.screenshot({ path: path.join(artifactRoot, `${safePrefix}-viewport.png`), fullPage: false });
  await page.screenshot({ path: path.join(artifactRoot, `${safePrefix}-full-page.png`), fullPage: true });
  const contentSection = page.locator('section[aria-label="Содержание входящего письма"]').first();
  if (await contentSection.count()) {
    await contentSection.screenshot({ path: path.join(artifactRoot, `${safePrefix}-central.png`) });
  } else {
    await firstFrame.screenshot({ path: path.join(artifactRoot, `${safePrefix}-central.png`) });
  }
  await page.screenshot({ path: path.join(artifactRoot, `${safePrefix}-top.png`), fullPage: false });
  await setScrollPosition(page, firstFrame, 'bottom');
  await page.screenshot({ path: path.join(artifactRoot, `${safePrefix}-bottom.png`), fullPage: false });
  await setScrollPosition(page, firstFrame, 'top');

  return { source: source.map(sourceStats), scrollBefore, frames: metrics };
}

test('live /messages renders real HTML mail without disappearing content or overflow', async ({ page }) => {
  test.setTimeout(180_000);
  let activeCase = 'initial';
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      const location = message.location();
      consoleErrors.push(`${activeCase}: ${message.text()} (${location.url}:${location.lineNumber})`);
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? ''}`));

  await loginThroughLiveApi(page);
  await page.goto('/messages', { waitUntil: 'networkidle' });
  expect(new URL(page.url()).pathname).toBe('/messages');

  const inboxResponse = await page.request.get('/api/mail/inbox');
  expect(inboxResponse.status()).toBe(200);
  const inbox = (await inboxResponse.json()).items as SourceMessage[];
  const evidence: Record<string, unknown> = { url: page.url(), viewports, cases: {}, runtime: { consoleErrors, pageErrors, failedRequests } };

  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const item of unmatchedCases) {
      activeCase = `${item.key}-${viewport.name}`;
      const source = inbox.filter((message) => message.subject.includes(item.subject));
      expect(source.length, `source message not found: ${item.subject}`).toBe(1);
      const frames = await openUnmatched(page, item.subject);
      const expectedNotice = sourceStats(source[0]).blockedRemoteImages > 0;
      const result = await captureCase(page, frames, item.key, viewport.name, source, expectedNotice);
      (evidence.cases as Record<string, unknown>)[`${item.key}-${viewport.name}`] = result;
    }

    const threadResponse = await page.request.get('/api/mail/threads?request_id=1055&supplier_id=2097');
    expect(threadResponse.status()).toBe(200);
    const threadMessages = (await threadResponse.json()).items as SourceMessage[];
    const plainSource = threadMessages.filter((message) => message.subject === 'Коммерческое предложение по насосам');
    expect(plainSource.length, 'plain text source message not found').toBeGreaterThan(0);
    activeCase = `plain-text-${viewport.name}`;
    const plainFrames = await openPlainThread(page);
    const plainResult = await captureCase(page, plainFrames, 'plain-text', viewport.name, plainSource, false);
    (evidence.cases as Record<string, unknown>)[`plain-text-${viewport.name}`] = plainResult;

    const cidResponse = await page.request.get('/api/mail/threads?request_id=1059&supplier_id=2436');
    expect(cidResponse.status()).toBe(200);
    const cidMessages = (await cidResponse.json()).items as SourceMessage[];
    // Message 167 is the real CID-only fixture in this controlled mailbox.
    // Its allowlisted HTML intentionally does not expose the unresolved cid:
    // source, but the server still reports that no remote image was blocked.
    expect(cidMessages.some((message) => message.id === 167 && message.has_remote_images === false), 'CID-only source message not found').toBe(true);
    expect(cidMessages.every((message) => sourceStats(message).blockedRemoteImages === 0), 'CID-only thread must not contain blocked remote images').toBe(true);
    activeCase = `cid-images-${viewport.name}`;
    const cidFrames = await openThread(page, 1059, 2436);
    const cidResult = await captureCase(page, cidFrames, 'cid-images', viewport.name, cidMessages, false);
    (evidence.cases as Record<string, unknown>)[`cid-images-${viewport.name}`] = cidResult;
  }

  const expectedSandboxWarnings = consoleErrors.filter((message) => message.includes("Blocked script execution in 'about:srcdoc' because the document's frame is sandboxed and the 'allow-scripts' permission is not set."));
  const unexpectedConsoleErrors = consoleErrors.filter((message) => !message.includes("Blocked script execution in 'about:srcdoc' because the document's frame is sandboxed and the 'allow-scripts' permission is not set."));
  (evidence.runtime as Record<string, unknown>).expectedSandboxWarnings = expectedSandboxWarnings;
  (evidence.runtime as Record<string, unknown>).unexpectedConsoleErrors = unexpectedConsoleErrors;
  fs.writeFileSync(path.join(artifactRoot, 'metrics.json'), JSON.stringify(evidence, null, 2), 'utf8');
  expect(unexpectedConsoleErrors, 'live /messages must not emit unexpected console errors').toEqual([]);
  expect(pageErrors, 'live /messages must not emit uncaught errors').toEqual([]);
});
