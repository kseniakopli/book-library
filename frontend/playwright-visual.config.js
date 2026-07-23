// Визуальная регрессия (задача 86). Отдельный конфиг от smoke (з.68):
//  - smoke гоняет живой сценарий против настоящего бэкенда;
//  - visual мокает API, бэкенд не нужен — только dev-сервер для статики.
// Запуск: npm run test:visual  (эталоны: npm run test:visual -- --update-snapshots)
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /visual\.spec\.js/,      // только визуальные тесты
  timeout: 30000,
  // фиксированный размер окна — размер влияет на раскладку и скриншот
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1280, height: 900 },
  },
  // допускаем крошечный анти-алиасинг-шум, но ловим реальные сдвиги
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled" },
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60000,
  },
});
