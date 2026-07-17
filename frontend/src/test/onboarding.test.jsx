// Онбординг (задача 21): пустая библиотека → три шага + наполнение примерами.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";
import { db } from "./server";

test("пустая библиотека показывает онбординг, примеры наполняют полки", async () => {
  db.books = [];
  renderApp();

  expect(
    await screen.findByText("Добро пожаловать в Nocturne"),
  ).toBeInTheDocument();
  // полок нет
  expect(screen.queryByText("Здесь пока пусто")).not.toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: /Наполнить примерами/ }),
  );

  // примеры добавились, полки появились, онбординг исчез
  expect(await screen.findByText("Мастер и Маргарита")).toBeInTheDocument();
  expect(
    screen.queryByText("Добро пожаловать в Nocturne"),
  ).not.toBeInTheDocument();
});

test("кнопка онбординга открывает модалку поиска", async () => {
  db.books = [];
  renderApp();
  await screen.findByText("Добро пожаловать в Nocturne");

  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить первую книгу" }),
  );
  expect(await screen.findByRole("dialog")).toBeInTheDocument();
});
