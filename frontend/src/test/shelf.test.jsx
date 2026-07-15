// Полка: листание стрелками, граничные состояния кнопок.
import { test, expect } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Shelf from "../components/Shelf";

const books = Array.from({ length: 7 }, (_, i) => ({
  id: i + 1,
  title: `Книга ${i + 1}`,
  author: "Автор",
  status: "want",
  rating: null,
  cover_url: null,
}));

// Полка управляемая — состояние листания живёт у родителя
function Wrapper() {
  const [start, setStart] = useState(0);
  return (
    <Shelf
      title="Тестовая"
      books={books}
      onSelect={() => {}}
      start={start}
      onStart={setStart}
    />
  );
}

test("листание полки: стрелки и границы", async () => {
  render(<Wrapper />);
  // ширина jsdom по умолчанию 1024px → 5 карточек в ряду
  expect(screen.getByText("Книга 1")).toBeInTheDocument();
  expect(screen.queryByText("Книга 6")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Вперёд" }));
  expect(screen.getByText("Книга 6")).toBeInTheDocument();
  expect(screen.getByText("Книга 7")).toBeInTheDocument();
  expect(screen.queryByText("Книга 1")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вперёд" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Назад" }));
  expect(screen.getByText("Книга 1")).toBeInTheDocument();
});

test("пустая полка и полка-заглушка", () => {
  render(<Shelf title="Пустая" books={[]} onSelect={() => {}} />);
  expect(screen.getByText("Здесь пока пусто")).toBeInTheDocument();

  render(<Shelf title="Скоро" placeholder="Скоро — на основе прочитанного" />);
  expect(
    screen.getByText("Скоро — на основе прочитанного"),
  ).toBeInTheDocument();
});
