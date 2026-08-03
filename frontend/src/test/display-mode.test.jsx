// Режим отображения полки (задача 66): переключатель обложки ↔ символы.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("переключатель полки: обложки ↔ символы, выбор запоминается", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  // По умолчанию — обложки. ⚠ Задача 110: у кнопки осталась одна иконка
  // (▦ / ◈), поэтому состояние читаем из aria-label, а не из текста, —
  // и заодно проверяем то, что услышит скринридер.
  const toggle = screen.getByRole("button", { name: /Вид полки/ });
  expect(toggle).toHaveAccessibleName(/обложки/);

  // переключаем на символы — подтягивается design-summary, кнопка меняет подпись
  await userEvent.click(toggle);
  expect(
    screen.getByRole("button", { name: /Вид полки/ }),
  ).toHaveAccessibleName(/символы/);

  // выбор сохранён в localStorage (на этапе 9 переедет в кабинет)
  expect(localStorage.getItem("displayMode")).toBe("symbols");
});
