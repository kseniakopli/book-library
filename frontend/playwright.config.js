// E2E-smoke (задача 68). Гоняет сквозной сценарий в реальном браузере против
// живого стека. Фронтенд-дев-сервер поднимается автоматически; БЭКЕНД (uvicorn
// на :8000) нужно запустить отдельно — Vite проксирует туда /api.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // визуальные тесты — в своём конфиге (playwright-visual.config.js): им нужны
  // моки API, а не живой бэкенд. Сюда не подхватываем.
  testIgnore: /visual\.spec\.js/,
  timeout: 30000,
  expect: { timeout: 5000 },
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true, // если dev-сервер уже запущен — используем его
    timeout: 60000,
  },
});
