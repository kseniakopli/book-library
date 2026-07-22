// Панель «Атмосфера»: одна кнопка наполняет все категории, вкладки переключаются.
import { test, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

test("подбор атмосферы наполняет все категории разом", async () => {
  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });
  expect(await screen.findByText(/Пока пусто/)).toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: "Подобрать атмосферу" }),
  );

  // категория «Музыка» активна по умолчанию
  expect(await screen.findByText("Song A")).toBeInTheDocument();

  // вкладки категорий
  await userEvent.click(screen.getByRole("button", { name: "Угощения" }));
  expect(await screen.findByText("Глинтвейн")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Ароматы" }));
  expect(await screen.findByText("Сандал")).toBeInTheDocument();

  // переключение источника внутри категории
  await userEvent.click(screen.getByRole("button", { name: "ChatGPT" }));
  expect(screen.getByText("ChatGPT explanation")).toBeInTheDocument();

  // кнопка сменила подпись — подборки уже есть
  expect(
    screen.getByRole("button", { name: "Обновить атмосферу" }),
  ).toBeInTheDocument();
});

test("оценка подборки: 👍 включается и снимается (задача 26)", async () => {
  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });
  await userEvent.click(
    screen.getByRole("button", { name: "Подобрать атмосферу" }),
  );
  await screen.findByText("Song A");

  const like = await screen.findByRole("button", { name: "Понравилось" });
  expect(like).toHaveAttribute("aria-pressed", "false");

  // клик → оценка ставится (кэш обновляется асинхронно — ждём перерисовку)
  await userEvent.click(like);
  await waitFor(() =>
    expect(like).toHaveAttribute("aria-pressed", "true"),
  );

  // повторный клик снимает оценку (toggle)
  await userEvent.click(like);
  await waitFor(() =>
    expect(like).toHaveAttribute("aria-pressed", "false"),
  );
});
