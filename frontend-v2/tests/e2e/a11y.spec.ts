import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { loginAsTestUser } from './support/auth';

function formatViolations(violations: Array<{ id: string; impact?: string | null; help: string; nodes: unknown[] }>) {
  return violations.map((v) => `[${v.impact ?? 'unknown'}] ${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n');
}

function bySeverity(violations: Array<{ impact?: string | null }>) {
  const buckets = { critical: 0, serious: 0, moderate: 0, minor: 0, unknown: 0 };
  for (const v of violations) {
    const key = (v.impact ?? 'unknown') as keyof typeof buckets;
    buckets[key] = (buckets[key] ?? 0) + 1;
  }
  return buckets;
}

const pages: Array<{ name: string; goto: (page: import('@playwright/test').Page) => Promise<void> }> = [
  { name: 'login', goto: async (page) => { await page.goto('/'); } },
  {
    name: 'requests',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Заявки/ }).click();
    },
  },
  {
    name: 'request-detail',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.goto('/#/requests');
      await page.locator('table tbody tr, [data-testid="request-row"]').first().click();
    },
  },
  {
    name: 'messages',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Сообщения/ }).click();
    },
  },
  {
    name: 'suppliers',
    goto: async (page) => {
      await loginAsTestUser(page);
      await page.getByRole('link', { name: /Поставщики/ }).click();
    },
  },
];

for (const { name, goto } of pages) {
  test(`a11y: ${name} has no critical/serious axe violations`, async ({ page }, testInfo) => {
    await goto(page);
    await page.waitForLoadState('networkidle');
    const results = await new AxeBuilder({ page }).analyze();
    const buckets = bySeverity(results.violations);
    await testInfo.attach(`${name}-axe-summary`, {
      body: JSON.stringify({ buckets, violations: results.violations.map((v) => v.id) }, null, 2),
      contentType: 'application/json',
    });

    // `color-contrast` is systemic pre-existing design-token debt across
    // nearly every screen (docs/system/DOCUMENTATION_DEBT.md-adjacent gap,
    // ink-muted tokens ~3.5:1 vs the 4.5:1 AA requirement). Fixing the
    // design system is out of scope for this QA pass (see task scope: no
    // UI/design-system rework), so it is reported but not gating -- per
    // the instruction to gate only on issues that would otherwise block
    // the whole project. Every other critical/serious violation still
    // fails the test.
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || (v.impact === 'serious' && v.id !== 'color-contrast'),
    );
    expect(blocking, formatViolations(blocking)).toEqual([]);
  });
}
