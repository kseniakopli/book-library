// Выпадающие меню шапки (задача 110): разделы вместо ряда из семи кнопок.
import { test, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

const SLOW = { timeout: 5000 };

test("меню закрыто по умолчанию и открывается кликом", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  const trigger = screen.getByRole("button", { name: /Книги/ });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("menuitem", { name: "Авторы" })).toBeNull();

  await userEvent.click(trigger);

  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("menuitem", { name: "Авторы" })).toBeInTheDocument();
});

test("Esc закрывает меню и возвращает фокус на кнопку", async () => {
  // без возврата фокуса он улетает в body, и следующий Tab начинает
  // обход страницы заново — для клавиатуры это потеря места
  renderApp();
  await screen.findByText("Волшебная гора");

  const trigger = screen.getByRole("button", { name: /Книги/ });
  await userEvent.click(trigger);
  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("menuitem", { name: "Авторы" })).toBeNull();
  expect(trigger).toHaveFocus();
});

test("личное меню собрано под именем пользователя", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("button", { name: /Ксения/ }));

  const menu = screen.getByRole("menu");
  expect(within(menu).getByRole("menuitem", { name: "Рекомендации" })).toBeInTheDocument();
  expect(within(menu).getByRole("menuitem", { name: "Статистика" })).toBeInTheDocument();
  expect(within(menu).getByRole("menuitem", { name: "Импорт CSV" })).toBeInTheDocument();
  expect(within(menu).getByRole("menuitem", { name: "Экспорт CSV" })).toBeInTheDocument();
  expect(within(menu).getByRole("menuitem", { name: "Выйти" })).toBeInTheDocument();
});

test("из меню можно перейти к рекомендациям", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("button", { name: /Ксения/ }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Рекомендации" }));

  expect(
    await screen.findByRole("heading", { name: /Рекомендации/ }, SLOW),
  ).toBeInTheDocument();
});

test("из меню можно перейти к списку авторов", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("button", { name: /Книги/ }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Авторы" }));

  expect(
    await screen.findByRole("heading", { name: "Авторы" }, SLOW),
  ).toBeInTheDocument();
  // число книг считается по каталогу сервиса и склоняется
  expect(await screen.findByText("2 книги")).toBeInTheDocument();
  expect(screen.getByText("1 книга")).toBeInTheDocument();
});

test("рекомендаций на главной больше нет", async () => {
  // задача 110: главная — только про то, что уже есть на полке
  renderApp();
  await screen.findByText("Волшебная гора");

  expect(
    screen.queryByRole("button", { name: "Подобрать рекомендации" }),
  ).toBeNull();
});
