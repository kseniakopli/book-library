// Книга из общего каталога, которой нет на своей полке (правка 03.08).
//
// Нашла Ксения на проде: книга 211 отдавала «Книга не найдена» всем, кроме
// того, кто её добавил. Книга — общая сущность, её страница обязана
// открываться у всех; личных полей при этом просто нет.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";
import { server } from "./server";

const CATALOG_BOOK = {
  id: 211,
  title: "Понедельник начинается в субботу",
  author: "Аркадий и Борис Стругацкие",
  authors: [
    { id: 20, name: "Аркадий Стругацкий" },
    { id: 21, name: "Борис Стругацкий" },
  ],
  cover_url: null,
  description: null,
  enrich_status: "ready",
  on_shelf: false,
  status: null,
  rating: null,
  read_at: null,
  user_id: null,
  genres: [],
};

function serveCatalogBook() {
  server.use(
    http.get("/api/v1/books/211", () => HttpResponse.json(CATALOG_BOOK)),
  );
}

test("книга не с моей полки открывается", async () => {
  serveCatalogBook();
  renderApp("/books/211");

  expect(
    await screen.findByRole("heading", {
      name: "Понедельник начинается в субботу",
    }),
  ).toBeInTheDocument();
});

test("вместо статусов предлагается положить книгу на полку", async () => {
  serveCatalogBook();
  renderApp("/books/211");
  await screen.findByRole("heading", { name: /Понедельник/ });

  expect(screen.getByText("Этой книги нет на вашей полке.")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /В «Хочу прочитать»/ }),
  ).toBeInTheDocument();
  // статусов быть не может: они живут в userbook, которого для меня нет
  expect(screen.queryByRole("button", { name: "Прочитана" })).toBeNull();
});

test("личных действий у чужой книги нет", async () => {
  // витрина и удаление — про свою полку; «вечер» и карточка строятся
  // из общей атмосферы и остаются
  serveCatalogBook();
  renderApp("/books/211");
  await screen.findByRole("heading", { name: /Понедельник/ });

  expect(screen.queryByRole("button", { name: /Удалить/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /витрин/i })).toBeNull();
  expect(screen.getByRole("link", { name: /Начать вечер/ })).toBeInTheDocument();
});

test("соавторы показаны по-русски и каждый своей ссылкой", async () => {
  serveCatalogBook();
  renderApp("/books/211");
  await screen.findByRole("heading", { name: /Понедельник/ });

  expect(
    screen.getByRole("link", { name: "Аркадий Стругацкий" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Борис Стругацкий" }),
  ).toBeInTheDocument();
});
