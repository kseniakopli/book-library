// Публичная витрина (задача 30): открыта БЕЗ входа — это её смысл.
import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderApp } from "./utils";
import { server } from "./server";

test("витрина открывается гостю, без страницы входа", async () => {
  // /auth/me отвечает 401 — гость. Витрина всё равно должна открыться.
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

  renderApp("/u/ksenia");

  expect(await screen.findByText("Волшебная гора")).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Войти через Google" }),
  ).not.toBeInTheDocument();
});

test("страница книги в витрине показывает атмосферу", async () => {
  server.use(
    http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ detail: "Нужно войти" }, { status: 401 }),
    ),
  );

  renderApp("/u/ksenia/books/1");

  expect(
    await screen.findByRole("heading", { name: "Волшебная гора" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Song A")).toBeInTheDocument();
  // ничего личного: оценки на витрине нет
  expect(screen.queryByText(/9\/10/)).not.toBeInTheDocument();
});
