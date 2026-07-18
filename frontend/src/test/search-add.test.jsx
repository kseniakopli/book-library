// Модалка «Найти книгу»: поиск с debounce, добавление, закрытие по Esc.
import { test, expect } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("поиск во внешнем каталоге и добавление книги", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить книгу" }),
  );
  const dialog = await screen.findByRole("dialog");

  await userEvent.type(
    within(dialog).getByPlaceholderText("Название или автор…"),
    "гарри",
  );
  // debounce 300 мс + запрос — findByText ждёт до секунды
  expect(
    await screen.findByText("Гарри Поттер и философский камень"),
  ).toBeInTheDocument();

  await userEvent.click(
    screen.getByText("Гарри Поттер и философский камень"),
  );

  // задача 18: шаг выбора статуса; по умолчанию «Хочу прочитать»
  expect(
    within(dialog).getByRole("button", { name: "Хочу прочитать" }),
  ).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Добавить" }),
  );

  // модалка закрылась, книга появилась на полке «Хочу прочитать»
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(
    await screen.findByText(/Гарри Поттер и философский камень/),
  ).toBeInTheDocument();
});

test("для «Прочитана» появляется дата, «Не помню» её гасит", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить книгу" }),
  );
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(
    within(dialog).getByPlaceholderText("Название или автор…"),
    "гарри",
  );
  await userEvent.click(
    await screen.findByText("Гарри Поттер и философский камень"),
  );

  // даты нет, пока статус не «Прочитана»
  expect(screen.queryByLabelText("Дата прочтения:")).not.toBeInTheDocument();

  await userEvent.click(
    within(dialog).getByRole("button", { name: "Прочитана" }),
  );
  const dateInput = screen.getByLabelText("Дата прочтения:");
  expect(dateInput).toBeEnabled();

  await userEvent.click(screen.getByLabelText("Не помню"));
  expect(dateInput).toBeDisabled();
});

test("книга из локального каталога помечена и недоступна, если уже на полке", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить книгу" }),
  );
  const dialog = await screen.findByRole("dialog");

  await userEvent.type(
    within(dialog).getByPlaceholderText("Название или автор…"),
    "Манн",
  );
  // результат из локального каталога с пометкой «уже у вас»
  expect(await within(dialog).findByText("уже у вас")).toBeInTheDocument();
  // кнопка результата отключена — книга уже на полке
  const item = within(dialog)
    .getByText("уже у вас")
    .closest("button");
  expect(item).toBeDisabled();
});

test("каталог книгу не знает — добавление вручную", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить книгу" }),
  );
  const dialog = await screen.findByRole("dialog");

  // MSW отвечает пустой выдачей на всё, кроме «гарри»
  await userEvent.type(
    within(dialog).getByPlaceholderText("Название или автор…"),
    "Лихо. Медь и мед",
  );
  await screen.findByText(/Ничего не найдено/);
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Добавить вручную" }),
  );

  // название предзаполнено запросом; без автора «Добавить» неактивна
  expect(within(dialog).getByLabelText("Название")).toHaveValue(
    "Лихо. Медь и мед",
  );
  const addButton = within(dialog).getByRole("button", { name: "Добавить" });
  expect(addButton).toBeDisabled();

  await userEvent.type(within(dialog).getByLabelText("Автор"), "Яна Лехчина");
  expect(addButton).toBeEnabled();
  await userEvent.click(addButton);

  // модалка закрылась, книга на полке
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(await screen.findByText(/Лихо. Медь и мед/)).toBeInTheDocument();
});

test("короткий запрос не ищет, показывает подсказку", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.click(
    screen.getByRole("button", { name: "+ Добавить книгу" }),
  );
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(
    within(dialog).getByPlaceholderText("Название или автор…"),
    "га",
  );
  expect(
    await screen.findByText("Введите хотя бы 3 символа"),
  ).toBeInTheDocument();
});

test("Esc закрывает модалку и возвращает фокус на кнопку", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  const addButton = screen.getByRole("button", { name: "+ Добавить книгу" });

  await userEvent.click(addButton);
  await screen.findByRole("dialog");

  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(addButton).toHaveFocus();
});
