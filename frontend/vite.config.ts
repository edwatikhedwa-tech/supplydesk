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
  define: {
    'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || ''),
    'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY || ''),
  },
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
    // Keep 5173 as the preferred preview port, but let Vite choose the next
    // available port when another preview process is already running.
    port: Number(process.env.PORT || process.env.VITE_PORT || 5173),
    strictPort: false,
    allowedHosts: ['.vercel.run'],
    proxy: {
      '/api': runtime.baseUrl,
      '/oauth': runtime.baseUrl,
    },
  },
});
