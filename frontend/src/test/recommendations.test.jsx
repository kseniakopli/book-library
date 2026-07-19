// Полка «Рекомендации» (этап 8): подбор по кнопке и добавление совета в библиотеку.
import { test, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("до генерации полка зовёт подобрать рекомендации", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  // ждём, пока догрузится запрос рекомендаций — до этого полка ещё «пустая»
  expect(
    await screen.findByText(/Нажмите «Подобрать рекомендации»/),
  ).toBeInTheDocument();
});

test("рекомендации подбираются по кнопке и добавляются в «Хочу прочитать»", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(
    screen.getByRole("button", { name: "Подобрать рекомендации" }),
  );

  // совет с обоснованием
  expect(await screen.findByText("Тень ветра")).toBeInTheDocument();
  expect(screen.getByText(/Готическая тайна/)).toBeInTheDocument();
  // кнопка сменилась на «Обновить» — набор уже есть
  expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();

  // добавляем совет в библиотеку
  await userEvent.click(
    screen.getByRole("button", { name: /В «Хочу прочитать»/ }),
  );

  // книга появилась и на полке «Хочу прочитать» (осталась и в рекомендациях)
  await waitFor(() =>
    expect(screen.getAllByText("Тень ветра").length).toBeGreaterThan(1),
  );
});
