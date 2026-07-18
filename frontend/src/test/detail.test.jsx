// Страница книги: смена статуса, появление оценки, несуществующая книга.
import { test, expect } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("смена статуса сохраняется и подсвечивается", async () => {
  renderApp("/books/2"); // «Дом огней», статус want
  const readingBtn = await screen.findByRole("button", { name: "Читаю" });
  expect(readingBtn).toHaveAttribute("aria-pressed", "false");

  await userEvent.click(readingBtn);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Читаю" }),
    ).toHaveAttribute("aria-pressed", "true"),
  );
});

test("оценка появляется только у прочитанной книги", async () => {
  renderApp("/books/2");
  await screen.findByRole("heading", { name: "Дом огней" });
  expect(screen.queryByLabelText("Оценка:")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Прочитана" }));
  expect(await screen.findByLabelText("Оценка:")).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Оценка:"), "8");
  await waitFor(() =>
    expect(screen.getByLabelText("Оценка:")).toHaveValue("8"),
  );
});

test("несуществующая книга — сообщение и возврат", async () => {
  renderApp("/books/999");
  expect(await screen.findByText("Книга не найдена.")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "← К библиотеке" }),
  ).toBeInTheDocument();
});

test("ручная правка книги: смена названия сохраняется (задача 3)", async () => {
  renderApp("/books/2");
  await screen.findByRole("heading", { name: "Дом огней" });

  await userEvent.click(screen.getByRole("button", { name: "Редактировать" }));
  const dialog = await screen.findByRole("dialog", { name: "Правка книги" });

  const titleInput = within(dialog).getByLabelText("Название");
  expect(titleInput).toHaveValue("Дом огней");

  await userEvent.clear(titleInput);
  const saveBtn = within(dialog).getByRole("button", { name: "Сохранить" });
  expect(saveBtn).toBeDisabled(); // пустое название сохранить нельзя

  await userEvent.type(titleInput, "Дом огней (перевод 2021)");
  expect(saveBtn).toBeEnabled();
  await userEvent.click(saveBtn);

  // модалка закрылась, заголовок страницы обновился
  await waitFor(() =>
    expect(
      screen.queryByRole("dialog", { name: "Правка книги" }),
    ).not.toBeInTheDocument(),
  );
  expect(
    await screen.findByRole("heading", { name: "Дом огней (перевод 2021)" }),
  ).toBeInTheDocument();
});

test("оформление подбирается автоматически, без кнопки (задача 57)", async () => {
  renderApp("/books/2");
  await screen.findByRole("heading", { name: "Дом огней" });
  // GET оформления пуст → компонент сам делает POST; statement появляется
  expect(
    await screen.findByText("Символ выбран для теста"),
  ).toBeInTheDocument();
  // кнопки больше нет
  expect(
    screen.queryByRole("button", { name: /оформ/i }),
  ).not.toBeInTheDocument();
});
