// Порядок книг на полках (просьба Ксении 19.07):
// «Прочитано» — по дате прочтения, «Хочу прочитать» — по дате добавления;
// в обоих случаях свежее сверху.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";

test("«Хочу прочитать»: недавно добавленные — первыми", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  // порядок заголовков карточек в DOM = порядок на полках
  const titles = screen
    .getAllByRole("heading", { level: 3 })
    .map((h) => h.textContent);

  // «Замок Броуди» добавлена 05.07, «Дом огней» — 02.07 → Замок выше
  expect(titles.indexOf("Замок Броуди")).toBeLessThan(
    titles.indexOf("Дом огней"),
  );
});
