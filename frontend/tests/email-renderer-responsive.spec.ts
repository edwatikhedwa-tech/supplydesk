import { test, expect } from '@playwright/test';

const viewports = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'desktop', width: 1640, height: 900 },
];

test('source-like HTML keeps its composition at supported widths', async ({ page }, testInfo) => {
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto('/iframe.html?id=mail-emailrenderer--original-layout&viewMode=story', { waitUntil: 'networkidle' });

    const frame = page.locator('iframe[title="Содержимое письма"]');
    await expect(frame).toBeVisible();
    const metrics = await frame.evaluate((element) => {
      const iframe = element as HTMLIFrameElement;
      const doc = iframe.contentDocument;
      const body = doc?.body;
      const blueCard = doc?.querySelector<HTMLElement>('.email-card-blue');
      const button = doc?.querySelector<HTMLElement>('.email-button');
      return {
        outerClientWidth: document.documentElement.clientWidth,
        outerScrollWidth: document.documentElement.scrollWidth,
        emailClientWidth: doc?.documentElement.clientWidth ?? 0,
        emailScrollWidth: doc?.documentElement.scrollWidth ?? 0,
        bodyText: body?.innerText ?? '',
        blueBackground: blueCard ? getComputedStyle(blueCard).backgroundColor : '',
        buttonBackground: button ? getComputedStyle(button).backgroundColor : '',
        iframeWidth: Math.round(iframe.getBoundingClientRect().width),
      };
    });

    expect(metrics.outerScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(metrics.outerClientWidth + 1);
    expect(metrics.emailScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(metrics.emailClientWidth + 1);
    expect(metrics.bodyText).toContain('ПИСЬМА ИЗ ВСЕХ СЕРВИСОВ');
    expect(metrics.blueBackground).toBe('rgb(20, 120, 242)');
    expect(metrics.buttonBackground).toBe('rgb(23, 25, 28)');
    expect(metrics.iframeWidth).toBeLessThanOrEqual(viewport.width);

    await page.screenshot({
      path: testInfo.outputPath(`email-renderer-original-layout-${viewport.name}.png`),
      fullPage: true,
    });
  }
});

test('plain text preserves whitespace without rebuilding it into arbitrary paragraphs', async ({ page }) => {
  await page.goto('/iframe.html?id=mail-emailrenderer--plain-text&viewMode=story', { waitUntil: 'networkidle' });
  const frame = page.locator('iframe[title="Содержимое письма"]');
  await expect(frame).toBeVisible();
  const plainText = await frame.evaluate((element) => {
    const body = (element as HTMLIFrameElement).contentDocument?.body;
    const content = body?.querySelector<HTMLElement>('.email-plain-text');
    return { text: content?.textContent ?? '', whiteSpace: content ? getComputedStyle(content).whiteSpace : '' };
  });
  expect(plainText.text).toContain('Здравствуйте!\n\nЭто обычное текстовое письмо.');
  expect(plainText.whiteSpace).toBe('pre-wrap');
});

test('inline CID image is included in the iframe height at every supported width', async ({ page }) => {
  const viewports = [
    { width: 390, height: 844 },
    { width: 1024, height: 768 },
    { width: 1440, height: 900 },
    { width: 1640, height: 900 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto('/iframe.html?id=mail-emailrenderer--cid-image&viewMode=story', { waitUntil: 'networkidle' });
    const frame = page.locator('iframe[title="Содержимое письма"]');
    await expect(frame).toBeVisible();

    await expect.poll(
      () => frame.evaluate((element) => Math.round(element.getBoundingClientRect().height)),
      { timeout: 5_000 },
    ).toBeGreaterThan(160);

    const metrics = await frame.evaluate((element) => {
      const iframe = element as HTMLIFrameElement;
      const doc = iframe.contentDocument;
      const image = doc?.querySelector<HTMLImageElement>('img');
      const frameRect = iframe.getBoundingClientRect();
      const imageRect = image?.getBoundingClientRect();
      return {
        outerClientWidth: document.documentElement.clientWidth,
        outerScrollWidth: document.documentElement.scrollWidth,
        emailClientWidth: doc?.documentElement.clientWidth ?? 0,
        emailScrollWidth: doc?.documentElement.scrollWidth ?? 0,
        frameHeight: Math.round(frameRect.height),
        imageBottom: imageRect ? Math.round(imageRect.bottom) : 0,
        imageSrc: image?.getAttribute('src') ?? '',
        imageComplete: image?.complete ?? false,
        imageNaturalWidth: image?.naturalWidth ?? 0,
        bodyText: doc?.body?.innerText ?? '',
      };
    });

    expect(metrics.outerScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(metrics.outerClientWidth + 1);
    expect(metrics.emailScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(metrics.emailClientWidth + 1);
    expect(metrics.frameHeight, JSON.stringify(metrics)).toBeGreaterThanOrEqual(metrics.imageBottom + 4);
    expect(metrics.imageSrc).toMatch(/^data:image\/png;base64,/);
    expect(metrics.imageComplete).toBe(true);
    expect(metrics.imageNaturalWidth).toBeGreaterThan(0);
    expect(metrics.bodyText).toContain('Текст письма должен отображаться');
  }
});
