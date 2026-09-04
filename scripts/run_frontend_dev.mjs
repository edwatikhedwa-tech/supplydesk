import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const env = {
  ...process.env,
  // Normal frontend development is an owner session and therefore canonical.
  // An explicit RUNTIME_PURPOSE=AUTOMATED_TEST + SAFE_TEST remains supported.
  RUNTIME_PURPOSE: process.env.RUNTIME_PURPOSE || 'OWNER_SESSION',
};
const args = process.argv.slice(2);
const commandIndex = args.indexOf('--command');
const viteCommand = commandIndex >= 0 ? args[commandIndex + 1] : 'dev';
if (commandIndex >= 0 && !viteCommand) {
  console.error('FAIL: --command requires a Vite command.');
  console.error('STOP: Vite was not started.');
  process.exit(3);
}
const viteArgs = commandIndex >= 0
  ? args.filter((_, index) => index !== commandIndex && index !== commandIndex + 1)
  : args;
const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const child = spawn(command, ['vite', viteCommand, ...viteArgs], {
  cwd: fileURLToPath(new URL('../frontend/', import.meta.url)),
  env,
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

child.on('error', (error) => {
  console.error(`FAIL: could not start Vite: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
