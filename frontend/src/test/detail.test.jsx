// Страница книги: смена статуса, появление оценки, несуществующая книга.
import { test, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
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
