// Общая настройка тестов: jest-dom матчеры, MSW-сервер, сброс состояния.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { server, resetDb } from "./server";

// fetch в Node требует абсолютный URL, а приложение ходит на относительные
// ("/books"). Дополняем их фиктивным origin — MSW матчит по пути.
const originalFetch = globalThis.fetch;
globalThis.fetch = (input, init) =>
  originalFetch(
    typeof input === "string" && input.startsWith("/")
      ? new URL(input, "http://localhost").href
      : input,
    init,
  );

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetDb();
  localStorage.clear();
  sessionStorage.clear();
});

afterAll(() => server.close());
