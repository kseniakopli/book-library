// Полка «Рекомендации» (этап 8): подбор по кнопке и добавление совета в библиотеку.
import { test, expect } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
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

  // советы с обоснованием — от обеих моделей (с 20.07)
  expect(await screen.findByText("Тень ветра")).toBeInTheDocument();
  expect(screen.getByText(/Готическая тайна/)).toBeInTheDocument();
  expect(screen.getByText("Имя розы")).toBeInTheDocument();
  // у каждой карточки виден источник совета
  expect(screen.getByText("Claude")).toBeInTheDocument();
  expect(screen.getByText("ChatGPT")).toBeInTheDocument();
  // кнопка сменилась на «Обновить» — набор уже есть
  expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();

  // добавляем ПЕРВЫЙ совет в библиотеку (кнопка есть у каждой карточки —
  // ищем внутри карточки, а не по всей странице)
  const card = screen.getByText("Тень ветра").closest(".rec-card");
  await userEvent.click(
    within(card).getByRole("button", { name: /В «Хочу прочитать»/ }),
  );

  // книга появилась и на полке «Хочу прочитать» (осталась и в рекомендациях)
  await waitFor(() =>
    expect(screen.getAllByText("Тень ветра").length).toBeGreaterThan(1),
  );
});
