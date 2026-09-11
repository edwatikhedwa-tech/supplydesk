import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5183,
    // Fixed rather than left to Vite's auto-increment: the Yandex OAuth
    // session cookie is host-scoped to 127.0.0.1:8000 and only round-trips
    // correctly when the dev server is reached at a known, stable origin
    // (see scripts/start_server_and_open.ps1, which opens this exact URL).
    strictPort: true,
    proxy: {
      '/api': BACKEND_BASE_URL,
      '/oauth': BACKEND_BASE_URL,
    },
  },
})
