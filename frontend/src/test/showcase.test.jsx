// Публичная витрина (задача 30): открыта БЕЗ входа — это её смысл.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";
import { server } from "./server";

const asGuest = () =>
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

test("витрина открывается гостю, без страницы входа", async () => {
  // /auth/me отвечает 401 — гость. Витрина всё равно должна открыться.
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

  renderApp("/u/ksenia");

  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Войти через Google" }),
  ).not.toBeInTheDocument();
});

test("страница книги в витрине показывает атмосферу", async () => {
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

  renderApp("/u/ksenia/books/1");

  expect(
    await screen.findByRole("heading", { name: "Волшебная гора" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Song A")).toBeInTheDocument();
  // ничего личного: оценки на витрине нет
  expect(screen.queryByText(/9\/10/)).not.toBeInTheDocument();
});

// --- Витрина как вход в сервис (28.07) ---
// Гость приходит по QR с бумажной карточки и про nocturne ничего не знает:
// кроме книг ему нужно понять, что это, и получить способ остаться на связи.

test("в карточке ленты только название и автор", async () => {
  asGuest();
  renderApp("/u/ksenia");

  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(screen.getByText("Томас Манн")).toBeInTheDocument();
  // Настроение из паспорта решили не выводить: формулы у разных книг вышли
  // от трёх слов до трёх строк и ломали ровный ряд (28.07). Мок отдаёт
  // base_mood — проверяем, что страница его игнорирует.
  expect(screen.queryByText("туманная меланхолия")).not.toBeInTheDocument();
  // Стрелки листания в jsdom не проверить: там нет размеров, scrollWidth
  // и clientWidth равны нулю — лента всегда «помещается». Их поведение
  // проверяется в браузере (frontend/scripts/layout-audit.mjs).
});

test("витрина объясняет сервис и даёт оставить почту", async () => {
  asGuest();
  renderApp("/u/ksenia");

  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Что такое nocturne" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Печатная карточка" })).toBeInTheDocument();

  expect(screen.getByLabelText("Ваша почта")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Хочу попробовать" }),
  ).toBeInTheDocument();
});
