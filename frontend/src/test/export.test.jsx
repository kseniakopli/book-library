// Экспорт полки (задача 35): пункт меню ведёт прямо на эндпоинт выгрузки.
// Само скачивание проверить в jsdom нельзя (браузерное поведение), поэтому
// проверяем контракт ссылки — адрес и атрибут download.
//
// ⚠ Задача 110: кнопка уехала из шапки в меню под именем пользователя.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("в меню есть ссылка на выгрузку CSV", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("button", { name: /Ксения/ }));

  const link = screen.getByRole("menuitem", { name: "Экспорт CSV" });
  expect(link).toHaveAttribute("href", "/api/v1/export/shelf.csv");
  expect(link).toHaveAttribute("download");
});
