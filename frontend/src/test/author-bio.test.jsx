// Биография автора (задача 111): показ и правка на месте, только у админа.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";
import { server } from "./server";

const SLOW = { timeout: 5000 };

test("админ может написать биографию, и она появляется на странице", async () => {
  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "Томас Манн" }, SLOW);

  expect(screen.getByText("Биография не заполнена.")).toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: "Добавить биографию" }),
  );
  await userEvent.type(
    screen.getByLabelText("Биография автора"),
    "Немецкий писатель, нобелевский лауреат.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));

  expect(
    await screen.findByText("Немецкий писатель, нобелевский лауреат."),
  ).toBeInTheDocument();
});

test("отмена возвращает прежний текст", async () => {
  renderApp("/authors/7");
  await screen.findByRole("heading", { name: "Томас Манн" }, SLOW);

  await userEvent.click(
    screen.getByRole("button", { name: "Добавить биографию" }),
  );
  await userEvent.type(screen.getByLabelText("Биография автора"), "Черновик");
  await userEvent.click(screen.getByRole("button", { name: "Отмена" }));

  expect(screen.queryByLabelText("Биография автора")).toBeNull();
  expect(screen.getByText("Биография не заполнена.")).toBeInTheDocument();
});

test("не-админ не видит ни кнопки, ни пустого блока", async () => {
  // пустой блок с подписью «биографии нет» для читателя — шум:
  // сделать он с ним ничего не может
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
  await screen.findByRole("heading", { name: "Томас Манн" }, SLOW);

  expect(screen.queryByText("Биография не заполнена.")).toBeNull();
  expect(screen.queryByRole("button", { name: /биографию/ })).toBeNull();
});
