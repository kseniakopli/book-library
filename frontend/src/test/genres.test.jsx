// Жанры (задача 112): справочник, страница жанра, правка у книги.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";
import { server } from "./server";

const SLOW = { timeout: 5000 };

test("справочник жанров открывается из меню «Книги»", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("button", { name: /Книги/ }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Жанры" }));

  expect(
    await screen.findByRole("heading", { name: "Жанры" }, SLOW),
  ).toBeInTheDocument();
  // число книг считается по каталогу и склоняется
  expect(await screen.findByText("3 книги")).toBeInTheDocument();
  expect(screen.getByText("1 книга")).toBeInTheDocument();
});

test("страница жанра делит книги на полку и каталог", async () => {
  renderApp("/genres/1");

  expect(
    await screen.findByRole("heading", { name: "Детектив" }, SLOW),
  ).toBeInTheDocument();
  expect(screen.getByText("На полке")).toBeInTheDocument();
  expect(screen.getByText("Есть в каталоге")).toBeInTheDocument();
  expect(screen.getByText("Будденброки")).toBeInTheDocument();
});

test("админ проставляет жанры книге", async () => {
  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  await userEvent.click(
    await screen.findByRole("button", { name: "Проставить жанры" }),
  );
  await userEvent.type(screen.getByLabelText("Новый жанр"), "Модернизм");
  await userEvent.click(screen.getByRole("button", { name: "Добавить" }));
  await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));

  expect(await screen.findByRole("link", { name: "Модернизм" })).toBeInTheDocument();
});

test("одинаковый жанр не добавляется дважды", async () => {
  // сравнение без регистра: иначе «Детектив» и «детектив» станут двумя
  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  await userEvent.click(
    await screen.findByRole("button", { name: "Проставить жанры" }),
  );
  const input = screen.getByLabelText("Новый жанр");

  await userEvent.type(input, "Детектив{Enter}");
  await userEvent.type(input, "детектив{Enter}");

  expect(screen.getAllByText(/детектив/i)).toHaveLength(1);
});

test("в подсказках показаны ВСЕ жанры библиотеки, а не первые несколько", async () => {
  // Задача 120, найдено Ксенией на проде: в блоке «Уже есть» висел
  // slice(0, 8). Цена была не в удобстве, а в данных — жанра не видно
  // в подсказках, он набирается руками, и в базе появляется дубль
  // («Современная русская литература» с латинской буквой внутри).
  // Поэтому мок отдаёт заведомо больше восьми: вернётся slice — тест упадёт.
  const many = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    name: `Жанр ${i + 1}`,
    books: 1,
  }));
  server.use(
    http.get("/api/v1/genres", () => HttpResponse.json({ genres: many })),
  );

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });
  await userEvent.click(
    await screen.findByRole("button", { name: "Проставить жанры" }),
  );

  // последний по списку — тот, что первым пропадал при обрезке
  expect(
    await screen.findByRole("button", { name: "Жанр 12" }, SLOW),
  ).toBeInTheDocument();
});

test("не-админ видит жанры ссылками, но не может править", async () => {
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({
        id: 2,
        display_name: "Гость",
        email: "guest@example.com",
        avatar_url: null,
        is_admin: false,
      }),
    ),
  );

  renderApp("/books/1");
  await screen.findByRole("heading", { name: "Волшебная гора" });

  expect(screen.queryByRole("button", { name: /жанры/i })).toBeNull();
});
