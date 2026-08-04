// Список книг цикла (задача 89) после правки 03.08.
//
// Раньше том, которого нет на полке, был НЕ кликабелен: страница книги
// отдавала 404 всем, кроме владельца полки. Ограничение снято (книга — общая
// сущность каталога), и ссылка вернулась: про такую книгу как раз и хочется
// прочитать, ради этого цикл и показывает продолжение.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";

const SLOW = { timeout: 5000 };

test("книга не с полки в цикле — тоже ссылка", async () => {
  renderApp("/series/1");

  const link = await screen.findByRole("link", { name: "Тень за спиной" }, SLOW);
  expect(link).toHaveAttribute("href", "/books/77");
});

test("книга не с полки помечена «Нет на полке»", async () => {
  // формулировка важна: «Нет в библиотеке» было неточным — книга в базе есть,
  // её нет именно на полке читателя
  renderApp("/series/1");

  expect(await screen.findByText("Нет на полке", {}, SLOW)).toBeInTheDocument();
  expect(screen.queryByText("Нет в библиотеке")).toBeNull();
});

test("книга с полки показывает свой статус", async () => {
  renderApp("/series/1");

  expect(await screen.findByText("Прочитана", {}, SLOW)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "В лесной чаще" }),
  ).toHaveAttribute("href", "/books/1");
});
