import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

type RuntimeSurface = 'frontend' | 'browser' | 'storybook' | 'lighthouse';

export interface RuntimeGuardOptions {
  surface: RuntimeSurface;
  baseUrl?: string;
  backendUrl?: string;
}

export interface RuntimeGuardResult {
  purpose: string;
  mode: string;
  baseUrl: string;
  databaseClass: string;
  authMode: string;
  backendUrl?: string;
}

const REPOSITORY_ROOT = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const GUARD_PATH = path.join(REPOSITORY_ROOT, 'scripts', 'runtime_guard.py');

function parseGuardOutput(output: string): RuntimeGuardResult {
  const values = new Map<string, string>();
  for (const line of output.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator > 0) values.set(line.slice(0, separator), line.slice(separator + 1).trim());
  }
  return {
    purpose: values.get('RUNTIME_PURPOSE') ?? '',
    mode: values.get('RUNTIME_MODE') ?? '',
    baseUrl: values.get('BASE_URL') ?? '',
    databaseClass: values.get('DATABASE_CLASS') ?? '',
    authMode: values.get('AUTH_MODE') ?? '',
    backendUrl: values.get('BACKEND_BASE_URL'),
  };
}

export function assertRuntime(options: RuntimeGuardOptions): RuntimeGuardResult {
  const args = [GUARD_PATH, '--surface', options.surface];
  if (options.baseUrl) args.push('--base-url', options.baseUrl);
  if (options.backendUrl) args.push('--backend-url', options.backendUrl);
  const output = execFileSync('python', args, {
    cwd: REPOSITORY_ROOT,
    env: process.env,
    encoding: 'utf8',
  });
  process.stdout.write(output);
  return parseGuardOutput(output);
}
