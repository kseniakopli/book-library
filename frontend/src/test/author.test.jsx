// Страница автора (задача 97).
//
// Проверяем ровно то, ради чего она делалась: с книги можно перейти к автору,
// а на его странице книги разложены на две стопки — своя полка и то, что есть
// в каталоге, но не у тебя. Если стопки схлопнутся в одну, страница превратится
// в повтор поиска по полке.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("с книги можно перейти на страницу автора", async () => {
  renderApp("/books/1");

  const link = await screen.findByRole("link", { name: "Томас Манн" });
  await userEvent.click(link);

  expect(
    await screen.findByRole("heading", { name: "Томас Манн" }),
  ).toBeInTheDocument();
});

test("книги автора разложены на полку и каталог", async () => {
  renderApp("/authors/7");

  expect(
    await screen.findByRole("heading", { name: "На полке" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Волшебная гора")).toBeInTheDocument();

  // вторая стопка — книги того же автора, которых у читателя нет
  expect(
    screen.getByRole("heading", { name: "Есть в каталоге" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Будденброки")).toBeInTheDocument();
});

test("у книг автора показан год — в обеих стопках", async () => {
  // Задача 121: год есть и у книг с полки, и у каталожных. Вторые приходят
  // коротким словарём из роутера, и год туда пришлось добавлять отдельно —
  // без этого половина списка выглядела бы как книги без года.
  renderApp("/authors/7");

  await screen.findByRole("heading", { name: "На полке" });
  expect(screen.getByText("1924")).toBeInTheDocument();   // с полки
  expect(screen.getByText("1901")).toBeInTheDocument();   // из каталога
});

test("несуществующий автор — понятное сообщение, не пустая страница", async () => {
  renderApp("/authors/999");

  expect(await screen.findByText("Автор не найден.")).toBeInTheDocument();
});
