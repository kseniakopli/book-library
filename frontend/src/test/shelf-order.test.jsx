// Порядок книг на полках (просьба Ксении 19.07):
// «Прочитано» — по дате прочтения, «Хочу прочитать» — по дате добавления;
// в обоих случаях свежее сверху.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";
import { db } from "./server";

test("«Хочу прочитать»: недавно добавленные — первыми", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  // порядок заголовков карточек в DOM = порядок на полках
  const titles = screen
    .getAllByRole("heading", { level: 3 })
    .map((h) => h.textContent);

  // «Замок Броуди» добавлена 05.07, «Дом огней» — 02.07 → Замок выше
  expect(titles.indexOf("Замок Броуди")).toBeLessThan(
    titles.indexOf("Дом огней"),
  );
});

test("полки «Читаю» нет, пока нет книг с этим статусом", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  // заголовок полки — h2 «Читаю N»; в фикстуре таких книг нет
  expect(
    screen.queryByRole("heading", { level: 2, name: /Читаю/ }),
  ).not.toBeInTheDocument();
});

test("полка «Читаю» появляется и стоит первой", async () => {
  db.books.push({
    id: 4,
    title: "Сейчас читаю",
    author: "Автор",
    status: "reading",
    rating: null,
    cover_url: null,
    description: null,
    enrich_status: "ready",
    created_at: "2026-07-06T10:00:00",
    updated_at: "2026-07-06T10:00:00",
    read_at: null,
  });

  renderApp();
  expect(await screen.findByText("Сейчас читаю")).toBeInTheDocument();

  const shelves = screen
    .getAllByRole("heading", { level: 2 })
    .map((h) => h.textContent);
  expect(shelves[0]).toMatch(/Читаю/);   // самая верхняя полка
});
