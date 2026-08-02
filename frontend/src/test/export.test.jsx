// Экспорт полки (задача 35): кнопка ведёт прямо на эндпоинт выгрузки.
// Само скачивание проверить в jsdom нельзя (браузерное поведение), поэтому
// проверяем контракт ссылки — адрес и атрибут download.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";

test("в шапке есть ссылка на выгрузку CSV", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  const link = screen.getByTitle("Скачать свою полку в CSV");
  expect(link).toHaveAttribute("href", "/api/v1/export/shelf.csv");
  expect(link).toHaveAttribute("download");
});
