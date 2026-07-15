// Главная страница: полки, фильтр по библиотеке, роутинг на карточку книги.
import { test, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("полки показывают книги из API", async () => {
  renderApp();
  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(screen.getByText("Дом огней")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /Прочитано/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: /Хочу прочитать/ }),
  ).toBeInTheDocument();
});

test("фильтр по библиотеке сужает список", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");
  await userEvent.type(
    screen.getByPlaceholderText("Поиск по библиотеке…"),
    "манн",
  );
  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(screen.queryByText("Дом огней")).not.toBeInTheDocument();
});

test("клик по книге открывает её страницу, «К библиотеке» возвращает", async () => {
  renderApp();
  await userEvent.click(
    await screen.findByRole("button", { name: "Волшебная гора — Томас Манн" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Волшебная гора" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Роман о санатории в Альпах.")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "← К библиотеке" }));
  expect(await screen.findByText("Дом огней")).toBeInTheDocument();
});

test("карточка книги открывается с клавиатуры (Enter)", async () => {
  renderApp();
  const card = await screen.findByRole("button", {
    name: "Дом огней — Донато Карризи",
  });
  card.focus();
  await userEvent.keyboard("{Enter}");
  expect(
    await screen.findByRole("heading", { name: "Дом огней" }),
  ).toBeInTheDocument();
});
