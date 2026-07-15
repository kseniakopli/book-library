import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/books': 'http://127.0.0.1:8000',
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