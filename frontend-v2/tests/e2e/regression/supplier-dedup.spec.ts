import { test } from '@playwright/test';

/**
 * P0 supplier-identity duplication (GAP-003 / INV-SUP-002; see
 * docs/product/SUPPLIERS.md, docs/domain/SUPPLIER_MODEL.md and
 * docs/system/KNOWN_GAPS.md#GAP-003).
 *
 * The real, executable reproduction of this bug now lives at
 * tests/test_supplier_dedup_p0_regression.py -- it drives the actual
 * MailRepository.upsert_supplier / resolve_supplier_for_send code paths
 * production uses (not a UI click-through), and currently FAILS on purpose:
 * a supplier discovered by corporate domain gets a SECOND supplier row the
 * moment the same real company is contacted by a staff member's personal
 * email with no host known at send time. Run it with:
 *   .venv-test/Scripts/python.exe -m unittest tests.test_supplier_dedup_p0_regression -v
 *
 * There is intentionally no frontend/browser reproduction of this: the bug
 * is in server-side identity resolution, a browser click-through would only
 * re-test the same server call through more moving parts for no extra
 * signal. This file stays as the pointer other QA/regression suites expect
 * to find under tests/e2e/regression/.
 */
test.fixme(
  'see tests/test_supplier_dedup_p0_regression.py for the real, currently-failing reproduction of GAP-003',
  async () => {},
);
