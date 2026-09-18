import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Seeds the deterministic QA fixture (Request -> Supplier A/B/C, see
 * scripts/seed_qa_fixtures.py) into the disposable SAFE_TEST database before
 * the suite runs, so Messages/AI-assistant tests never have to SKIP for
 * lack of correspondence data. Idempotent -- safe to run on every
 * `npm run test:*` invocation. Never touches anything but the disposable
 * test database (the script itself refuses any other path).
 */
export default function globalSetup(): void {
  const repoRoot = path.resolve(__dirname, '../../../..');
  const python = process.platform === 'win32'
    ? path.join(repoRoot, '.venv-test', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv-test', 'bin', 'python');
  const script = path.join(repoRoot, 'scripts', 'seed_qa_fixtures.py');
  try {
    const output = execFileSync(python, [script], { cwd: repoRoot, encoding: 'utf8' });
    process.stdout.write(`[global-setup] ${output}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `[global-setup] Failed to seed QA fixtures via ${script}. Is the SAFE_TEST backend ` +
        `running (scripts/start_test_runtime.ps1 -Apply)? Original error: ${message}`,
    );
  }
}
