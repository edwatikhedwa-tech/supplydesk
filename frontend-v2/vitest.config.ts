import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Separate from vite.config.ts (dev/build) because `vite`'s own defineConfig
// has no `test` field in its types -- vitest/config re-exports one that does.
// Keeps the dev server config untouched; this file is picked up only by
// `npm run test`.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
    // Playwright owns tests/e2e/**; vitest's default include glob would
    // otherwise also pick up those .spec.ts files and fail to load them.
    exclude: ['node_modules/**', 'tests/e2e/**'],
  },
})
