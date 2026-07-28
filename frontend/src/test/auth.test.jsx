// Авторизация на фронте (этап 9): гость видит вход, админские кнопки — по праву.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";
import { server } from "./server";

test("гость видит страницу входа вместо библиотеки", async () => {
  // /auth/me отвечает 401 — «не вошёл»
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

  renderApp();
  expect(
    await screen.findByRole("link", { name: "Войти через Google" }),
  ).toBeInTheDocument();
  // книг не видно
  expect(screen.queryByText("Волшебная гора")).not.toBeInTheDocument();
});

test("не-админ не видит кнопок правки общих данных", async () => {
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({
        id: 2,
        display_name: "Гость",
        email: "guest@example.com",
        avatar_url: null,
        is_admin: false,
      }),
    ),
  );

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  // общие данные книги и атмосфера — админские
  expect(screen.queryByRole("button", { name: "Редактировать" })).toBeNull();
  expect(
    screen.queryByRole("button", { name: /Подобрать атмосферу|Обновить атмосферу/ }),
  ).toBeNull();
  // а своё — на месте: удалить книгу со своей полки можно
  expect(screen.getByRole("button", { name: /Удалить/ })).toBeInTheDocument();
});

test("админ видит имя в шапке и кнопку выхода", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  expect(screen.getByText(/Ксения/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Выйти" })).toBeInTheDocument();
});

// Проверки самого выхода здесь НЕТ намеренно. После logout приложение делает
// полную перезагрузку страницы (баг 26.07), а это настоящая навигация браузера —
// jsdom её не выполняет, а подмена window.location ломает базовый URL для fetch,
// и MSW перестаёт отвечать. Сценарий проверяется там, где есть реальный браузер:
// e2e/smoke.spec.js → «выход возвращает на страницу входа».
