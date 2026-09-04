import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const env = {
  ...process.env,
  RUNTIME_PURPOSE: process.env.RUNTIME_PURPOSE || 'VISUAL_ACCEPTANCE',
};
const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['lhci', 'autorun', ...process.argv.slice(2)], {
  cwd: fileURLToPath(new URL('../frontend/', import.meta.url)),
  env,
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

if (result.error) {
  console.error(`FAIL: could not start Lighthouse CI: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
