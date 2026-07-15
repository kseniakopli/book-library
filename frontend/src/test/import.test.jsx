// Импорт CSV: выбор файла → отчёт об импорте.
import { test, expect } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderApp } from "./utils";

test("импорт CSV показывает отчёт", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  const file = new File(["Название,Автор\nКнига,Автор"], "books.csv", {
    type: "text/csv",
  });
  // input скрыт (кнопка кликает его программно) — заполняем напрямую
  const input = screen.getByLabelText("Файл CSV для импорта");
  fireEvent.change(input, { target: { files: [file] } });

  expect(
    await screen.findByText(/Импортировано: 2, дубликаты: 1, пропущено: 0/),
  ).toBeInTheDocument();
});
