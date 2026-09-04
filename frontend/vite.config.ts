import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { assertRuntime } from './runtimeGuard';

const runtime = assertRuntime({
  surface: 'frontend',
  baseUrl: process.env.BACKEND_BASE_URL,
});

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': runtime.baseUrl,
      '/oauth': runtime.baseUrl,
    },
  },
});
