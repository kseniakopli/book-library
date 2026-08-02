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

/** Вход «от имени» обычного пользователя без прав админа. */
function asGuest() {
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
}

test("не-админ не видит кнопок правки общих данных", async () => {
  asGuest();

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  // общие данные книги — админские
  expect(screen.queryByRole("button", { name: "Редактировать" })).toBeNull();
  // а своё — на месте: удалить книгу со своей полки можно
  expect(screen.getByRole("button", { name: /Удалить/ })).toBeInTheDocument();
});

test("не-админ может собрать атмосферу, которой ещё нет", async () => {
  // Жалоба тестировщика 02.08: книга из каталога без атмосферы была тупиком —
  // музыка и угощения фоном не генерируются, а кнопка требовала прав админа.
  // По умолчанию мок отдаёт пустые подборки, то есть это и есть тот случай.
  asGuest();

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  expect(
    screen.getByRole("button", { name: "Подобрать атмосферу" }),
  ).toBeInTheDocument();
});

test("не-админ не может пересобрать готовую атмосферу", async () => {
  // Перегенерация переписывает подборку для всех, включая витринные книги,
  // чьи плейлисты уехали в печатные QR.
  asGuest();
  server.use(
    http.get("/api/v1/books/:id/atmosphere/:category", ({ params }) => {
      // паспорт оформления оставляем пустым: у него payload — ОБЪЕКТ с палитрами,
      // и подмена его списком треков ломает раскраску страницы книги
      const selections =
        params.category === "design"
          ? []
          : [
              {
                source: "Claude",
                payload: [{ title: "Song A", artist: "Artist A" }],
                explanation: "готовая подборка",
              },
            ];
      return HttpResponse.json({
        book_id: Number(params.id),
        category: params.category,
        selections,
      });
    }),
  );

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });
  // ⚠ Дождаться именно ДАННЫХ: пока запросы атмосферы в полёте, подборок нет,
  // и кнопка «Подобрать атмосферу» успевает отрисоваться — проверка сразу после
  // заголовка ловила это промежуточное состояние
  await screen.findByText("готовая подборка");

  expect(
    screen.queryByRole("button", { name: /Подобрать атмосферу|Обновить атмосферу/ }),
  ).toBeNull();
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
