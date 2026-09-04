import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const purposeIndex = args.indexOf('--purpose');
if (purposeIndex === -1 || !args[purposeIndex + 1]) {
  console.error('FAIL: run_playwright.mjs requires --purpose <RUNTIME_PURPOSE>.');
  console.error('STOP: browser tests were not started.');
  process.exit(3);
}

const purpose = args[purposeIndex + 1];
const playwrightArgs = args.filter((_, index) => index !== purposeIndex && index !== purposeIndex + 1);
const env = { ...process.env, RUNTIME_PURPOSE: purpose };
const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['playwright', 'test', ...playwrightArgs], {
  cwd: fileURLToPath(new URL('../frontend/', import.meta.url)),
  env,
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

if (result.error) {
  console.error(`FAIL: could not start Playwright: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
