/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Forward API calls to FastAPI so the browser sees a single origin.
    // This keeps auth cookies same-site and avoids CORS in development.
    // API_PROXY_TARGET points it elsewhere, for example when port 8000 is taken.
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Tests that render thousands of lines are slow on shared CI runners.
    testTimeout: 20_000,
  },
})
