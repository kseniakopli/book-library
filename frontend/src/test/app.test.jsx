// Главная страница: полки, фильтр по библиотеке, роутинг на карточку книги.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";
import { db } from "./server";

test("полки показывают книги из API", async () => {
  renderApp();
  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(screen.getByText("Дом огней")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /Прочитано/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /Хочу прочитать/ }),
  ).toBeInTheDocument();
});

test("фильтр по библиотеке сужает список", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.type(
    screen.getByPlaceholderText("Поиск по библиотеке…"),
    "манн",
  );
  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(screen.queryByText("Дом огней")).not.toBeInTheDocument();
});

test("поиск на главной находит книги из каталога не на полке (задача 90)", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.type(
    screen.getByPlaceholderText("Поиск по библиотеке…"),
    "тайное",
  );
  // книга из каталога (не на полке) — с кнопкой добавить
  expect(await screen.findByText("Тайное место")).toBeInTheDocument();
  expect(
    screen.getByText("Есть в базе, но не на вашей полке"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "+ На полку" }),
  ).toBeInTheDocument();
});

test("клик по книге открывает её страницу, «К библиотеке» возвращает", async () => {
  renderApp();
  await userEvent.click(
    await screen.findByRole("button", { name: "Волшебная гора — Томас Манн" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Волшебная гора" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Роман о санатории в Альпах.")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "← К библиотеке" }));
  expect(await screen.findByText("Дом огней")).toBeInTheDocument();
});

test("карточка книги открывается с клавиатуры (Enter)", async () => {
  renderApp();
  const card = await screen.findByRole("button", {
    name: "Дом огней — Донато Карризи",
  });
  card.focus();
  await userEvent.keyboard("{Enter}");
  expect(
    await screen.findByRole("heading", { name: "Дом огней" }),
  ).toBeInTheDocument();
});

test("позиция полки переживает уход на карточку и возврат", async () => {
  // 7 книг «Хочу прочитать»: при ширине jsdom (1024px) на полке 5 карточек,
  // значит есть вторая страница листания
  db.books = Array.from({ length: 7 }, (_, i) => ({
    id: i + 1,
    title: `Книга ${i + 1}`,
    author: "Автор",
    status: "want",
    rating: null,
    cover_url: null,
    description: null,
    enrich_status: "ready",
  }));

  renderApp();
  await screen.findByText("Книга 1");

  // листаем вперёд: видны книги 3–7
  await userEvent.click(screen.getByRole("button", { name: "Вперёд" }));
  expect(screen.getByText("Книга 6")).toBeInTheDocument();
  expect(screen.queryByText("Книга 1")).not.toBeInTheDocument();

  // уходим на карточку и возвращаемся
  await userEvent.click(
    screen.getByRole("button", { name: "Книга 6 — Автор" }),
  );
  await screen.findByRole("heading", { name: "Книга 6" });
  await userEvent.click(screen.getByRole("button", { name: "← К библиотеке" }));

  // полка открылась на той же странице листания, а не с начала
  expect(await screen.findByText("Книга 6")).toBeInTheDocument();
  expect(screen.queryByText("Книга 1")).not.toBeInTheDocument();
});
