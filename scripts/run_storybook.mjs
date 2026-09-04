import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const args = process.argv.slice(2);
const commandIndex = args.indexOf('--command');
const storybookCommand = commandIndex >= 0 ? args[commandIndex + 1] : 'dev';
if (commandIndex >= 0 && !storybookCommand) {
  console.error('FAIL: --command requires a Storybook command.');
  console.error('STOP: Storybook was not started.');
  process.exit(3);
}
const storybookArgs = commandIndex >= 0
  ? args.filter((_, index) => index !== commandIndex && index !== commandIndex + 1)
  : args;

const env = {
  ...process.env,
  RUNTIME_PURPOSE: process.env.RUNTIME_PURPOSE || 'AUTOMATED_TEST',
};
const repositoryRoot = fileURLToPath(new URL('../', import.meta.url));
const guard = spawnSync('python', [
  path.join(repositoryRoot, 'scripts', 'runtime_guard.py'),
  '--surface', 'storybook',
  '--base-url', 'http://127.0.0.1:6006',
  '--root', repositoryRoot,
], {
  cwd: repositoryRoot,
  env,
  encoding: 'utf8',
});
if (guard.stdout) process.stdout.write(guard.stdout);
if (guard.stderr) process.stderr.write(guard.stderr);
if (guard.error || guard.status !== 0) {
  if (guard.error) console.error(`FAIL: could not start runtime guard: ${guard.error.message}`);
  console.error('STOP: Storybook was not started.');
  process.exit(guard.status || 3);
}

const portArgs = storybookArgs.some((value) => value === '--port' || value === '-p');
if (storybookCommand === 'dev' && !portArgs) storybookArgs.push('--port', '6006');

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const child = spawn(command, ['storybook', storybookCommand, ...storybookArgs], {
  cwd: fileURLToPath(new URL('../frontend/', import.meta.url)),
  env,
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

child.on('error', (error) => {
  console.error(`FAIL: could not start Storybook: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
