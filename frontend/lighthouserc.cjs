const { spawnSync } = require('node:child_process');
const path = require('node:path');

const repositoryRoot = path.resolve(__dirname, '..');
const guardArgs = [path.join(repositoryRoot, 'scripts', 'runtime_guard.py'), '--surface', 'lighthouse'];
if (process.env.AUDIT_BASE_URL) guardArgs.push('--base-url', process.env.AUDIT_BASE_URL);
if (process.env.RUNTIME_BACKEND_URL) guardArgs.push('--backend-url', process.env.RUNTIME_BACKEND_URL);

const guard = spawnSync('python', guardArgs, {
  cwd: repositoryRoot,
  env: process.env,
  encoding: 'utf8',
});
if (guard.stdout) process.stdout.write(guard.stdout);
if (guard.stderr) process.stderr.write(guard.stderr);
if (guard.error || guard.status !== 0) {
  if (guard.error) console.error(`FAIL: could not start runtime guard: ${guard.error.message}`);
  console.error('STOP: Lighthouse was not started.');
  process.exit(guard.status || 3);
}

const baseUrlLine = (guard.stdout || '').split(/\r?\n/).find((line) => line.startsWith('BASE_URL: '));
const baseUrl = baseUrlLine ? baseUrlLine.slice('BASE_URL: '.length).trim() : null;
if (!baseUrl) {
  console.error('FAIL: runtime guard did not return BASE_URL.');
  console.error('STOP: Lighthouse was not started.');
  process.exit(3);
}

module.exports = {
  ci: {
    collect: {
      url: [`${baseUrl}/`],
      numberOfRuns: 1,
      settings: {
        preset: 'desktop',
        onlyCategories: ['performance', 'accessibility', 'best-practices'],
      },
    },
    assert: {
      assertions: {
        'categories:performance': ['warn', { minScore: 0.8 }],
        'categories:accessibility': ['warn', { minScore: 0.9 }],
        'categories:best-practices': ['warn', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: './artifacts/lighthouseci',
    },
  },
};
