import { test } from '@playwright/test';

/**
 * P0 supplier-identity duplication (see docs/product/SUPPLIERS.md and
 * ai/DEFERRED_FINDINGS.md). This test intentionally does NOT fix anything --
 * per the current task scope, P0 supplier deduplication stays untouched
 * until a baseline exists. This spec documents the concrete reported case
 * so a future fix has an executable acceptance target.
 *
 * Reported case: заявка №1059 (sfera.termo@yandex.ru). Two supplier rows
 * for one real company:
 *   - id 2837, external_key=termo-sfera.pro (has registry/finance data)
 *   - id 3315, external_key=sfera.termo@yandex.ru (holds the real thread,
 *     created via the outgoing-send path with no host, per
 *     request_suppliers.reason='Добавлен при отправке письма.')
 *
 * This exact production data does not exist in the disposable SAFE_TEST
 * fixture used by the rest of this suite, so the case cannot be exercised
 * end-to-end here without either seeding production-shaped fixtures (out of
 * scope for this QA pass) or reading production data from a test (never
 * allowed). Marked fixme rather than deleted or silently skipped, so it
 * stays visible as a tracked gap instead of a false green.
 */
test.fixme(
  'a request with two supplier rows for the same real company (external_key=host vs external_key=email) shows one merged supplier, not two',
  async () => {
    // Intentionally not implemented: requires the production-shaped fixture
    // described above. Do not mark this PASS without that data; do not
    // change canonical_companies/global_suppliers merge logic to make this
    // pass -- that is the P0 fix, a separate task.
  },
);
