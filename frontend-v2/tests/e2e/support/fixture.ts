import type { APIRequestContext } from '@playwright/test';

export const FIXTURE_REQUEST_NAME = 'QA Fixture — AI контекст (не удалять)';

interface CorrespondenceItem {
  id: number;
  request_id: number;
  supplier_id: number;
  request_name: string;
  supplier_name: string;
}

export interface QaFixture {
  requestId: number;
  supplierAId: number;
  threadAId: number;
  supplierCId: number;
  threadCId: number;
}

/**
 * Resolves the deterministic ids scripts/seed_qa_fixtures.py just created,
 * by name rather than assuming fixed autoincrement values (those depend on
 * whatever else exists in the disposable database this run). Call after
 * logging in.
 */
export async function loadQaFixture(request: APIRequestContext): Promise<QaFixture> {
  const response = await request.get('/api/correspondence');
  const body = (await response.json()) as { items: CorrespondenceItem[] };
  const items = body.items.filter((item) => item.request_name === FIXTURE_REQUEST_NAME);
  const a = items.find((item) => item.supplier_name.includes('КЕЙС А'));
  const c = items.find((item) => item.supplier_name.includes('КЕЙС В'));
  if (!a || !c) {
    throw new Error(
      `QA fixture not found via /api/correspondence (looked for request_name="${FIXTURE_REQUEST_NAME}"). ` +
        'Did scripts/seed_qa_fixtures.py run? (playwright.config.ts globalSetup should have run it.)',
    );
  }
  return {
    requestId: a.request_id,
    supplierAId: a.supplier_id,
    threadAId: a.id,
    supplierCId: c.supplier_id,
    threadCId: c.id,
  };
}
