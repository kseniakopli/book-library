// Страница автора (задача 97).
//
// Проверяем ровно то, ради чего она делалась: с книги можно перейти к автору,
// а на его странице книги разложены на две стопки — своя полка и то, что есть
// в каталоге, но не у тебя. Если стопки схлопнутся в одну, страница превратится
// в повтор поиска по полке.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";
import { server } from "./server";

test("с книги можно перейти на страницу автора", async () => {
  renderApp("/books/1");

  const link = await screen.findByRole("link", { name: "Томас Манн" });
  await userEvent.click(link);

  expect(
    await screen.findByRole("heading", { name: "Томас Манн" }),
  ).toBeInTheDocument();
});

test("книги автора разложены на полку и каталог", async () => {
  renderApp("/authors/7");

  expect(
    await screen.findByRole("heading", { name: "На полке" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Волшебная гора")).toBeInTheDocument();

  // вторая стопка — книги того же автора, которых у читателя нет
  expect(
    screen.getByRole("heading", { name: "Есть в каталоге" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Будденброки")).toBeInTheDocument();
});

test("у книг автора показан год — в обеих стопках", async () => {
  // Задача 121: год есть и у книг с полки, и у каталожных. Вторые приходят
  // коротким словарём из роутера, и год туда пришлось добавлять отдельно —
  // без этого половина списка выглядела бы как книги без года.
  renderApp("/authors/7");

  await screen.findByRole("heading", { name: "На полке" });
  expect(screen.getByText("1924")).toBeInTheDocument();   // с полки
  expect(screen.getByText("1901")).toBeInTheDocument();   // из каталога
});

test("админ заводит книгу автору — она уходит в каталог", async () => {
  // Задача 123: книга попадает во вторую стопку, а не на полку. Проверяем
  // именно это: смысл в библиографии, а не в том, что читатель у себя держит.
  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "Есть в каталоге" });

  await userEvent.click(screen.getByRole("button", { name: /Добавить книгу/ }));
  await userEvent.type(screen.getByLabelText("Поиск книги"), "Иосиф и его братья");

  // ничего не нашлось — заводим вручную
  const manual = await screen.findByRole(
    "button",
    { name: "Добавить вручную" },
    { timeout: 5000 },
  );
  await userEvent.click(manual);
  await userEvent.click(screen.getByRole("button", { name: /Добавить «/ }));

  expect(
    await screen.findByRole("link", { name: "Иосиф и его братья" }),
  ).toBeInTheDocument();
});

test("автора при ручном вводе не спрашивают — он берётся со страницы", async () => {
  // ⚠ Поле автора здесь было бы способом привязать книгу не туда: строку
  // всё равно ставит бэкенд из самой сущности (иначе «Thomas Mann» из Google
  // завёл бы второго Томаса Манна рядом с этим).
  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "Есть в каталоге" });

  await userEvent.click(screen.getByRole("button", { name: /Добавить книгу/ }));
  await userEvent.type(screen.getByLabelText("Поиск книги"), "Иосиф и его братья");
  await userEvent.click(
    await screen.findByRole("button", { name: "Добавить вручную" }, { timeout: 5000 }),
  );

  expect(screen.queryByLabelText("Автор книги")).toBeNull();
});

test("книгу, которая уже в базе, отсюда добавить нельзя", async () => {
  // Задача 123: она уже привязана к своему автору, и «привязать её сюда»
  // означало бы сменить ей автора — это делается правкой книги, где видно,
  // что именно меняешь. Поэтому строка показана, но выбрать её нельзя.
  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "Есть в каталоге" });

  await userEvent.click(screen.getByRole("button", { name: /Добавить книгу/ }));
  await userEvent.type(screen.getByLabelText("Поиск книги"), "тайное");

  const found = await screen.findByRole(
    "button",
    { name: /Тайное место/ },
    { timeout: 5000 },
  );
  expect(found).toBeDisabled();
  expect(screen.getByText("уже в библиотеке")).toBeInTheDocument();
});

test("не-админ книгу автору не заводит", async () => {
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

  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "На полке" });

  expect(screen.queryByRole("button", { name: /Добавить книгу/ })).toBeNull();
});

test("несуществующий автор — понятное сообщение, не пустая страница", async () => {
  renderApp("/authors/999");

  expect(await screen.findByText("Автор не найден.")).toBeInTheDocument();
});
