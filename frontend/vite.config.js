import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/books': {
        target: 'http://127.0.0.1:8000',
        // F5 или прямой заход на /books/3 — навигация браузера (Accept: text/html):
        // отдаём SPA, а не проксируем в API. Fetch из кода просит JSON — идёт в API.
        bypass: (req) =>
          req.headers.accept?.includes('text/html') ? '/index.html' : undefined,
      },
      '/search': 'http://127.0.0.1:8000',
      '/import': 'http://127.0.0.1:8000',
    },
  },
  // Конфигурация Vitest (задача 20): jsdom-окружение + общий setup с MSW
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    globals: true,
  },
})