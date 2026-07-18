// «Вечер с книгой» (задача 65): вход со страницы книги + пустое состояние.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";

test("на странице книги есть вход в «вечер»", async () => {
  renderApp("/books/2");
  const link = await screen.findByRole("link", { name: /Начать вечер/ });
  expect(link).toHaveAttribute("href", "/books/2/evening");
});

test("сцена вечера открывается; без атмосферы — зовёт её подобрать", async () => {
  // MSW отдаёт пустую атмосферу (GET selections: []) → сцена в пустом состоянии
  renderApp("/books/2/evening");
  expect(
    await screen.findByRole("heading", { name: "Дом огней" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/подберите атмосферу/i)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Закрыть вечер" }),
  ).toBeInTheDocument();
});
