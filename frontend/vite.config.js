import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Задача 34: всё API под /api/v1 — префикс не пересекается с маршрутами SPA,
    // поэтому прежний bypass-хак для F5 на /books/N больше не нужен
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  // Конфигурация Vitest (задача 20): jsdom-окружение + общий setup с MSW
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    globals: true,
  },
})