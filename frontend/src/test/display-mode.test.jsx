// Режим отображения полки (задача 66): переключатель обложки ↔ символы.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("переключатель полки: обложки ↔ символы, выбор запоминается", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  // по умолчанию — обложки
  const toggle = screen.getByRole("button", { name: /Вид полки/ });
  expect(toggle).toHaveTextContent("Обложки");

  // переключаем на символы — подтягивается design-summary, кнопка меняет подпись
  await userEvent.click(toggle);
  expect(
    screen.getByRole("button", { name: /Вид полки/ }),
  ).toHaveTextContent("Символы");

  // выбор сохранён в localStorage (на этапе 9 переедет в кабинет)
  expect(localStorage.getItem("displayMode")).toBe("symbols");
});
