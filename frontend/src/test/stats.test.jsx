// Страница «Статистика» (задачи 24/63): цифры с бэкенда + AI-наблюдения по кнопке.
import { test, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

// recharts в тестах подменён целиком простыми обёртками. Две причины:
// 1) в jsdom у контейнера нулевые размеры — настоящие графики всё равно
//    ничего не нарисуют, только насыпят предупреждений;
// 2) реальный импорт библиотеки на ленивом роуте не укладывается в дефолтный
//    таймаут findBy (1 с) на холодном старте — тесты падали именно на этом.
// Проверяем свою логику: цифры, подписи, кнопку. Отрисовка столбиков — забота
// библиотеки, дублировать её тестом смысла нет.
vi.mock("recharts", () => {
  const Stub = ({ children }) => <div>{children}</div>;
  return {
    ResponsiveContainer: Stub,
    BarChart: Stub,
    Bar: Stub,
    Cell: Stub,
    CartesianGrid: Stub,
    XAxis: Stub,
    YAxis: Stub,
    Tooltip: Stub,
  };
});

// Запас по времени: страница за React.lazy, первый тест ждёт загрузки чанка.
const SLOW = { timeout: 5000 };

test("страница показывает итоги и топы", async () => {
  renderApp("/stats");

  // Ждём именно данные: заголовок появляется сразу, а карточки — после
  // ответа /stats (до этого на странице «Считаю…»).
  expect(await screen.findByText("706", {}, SLOW)).toBeInTheDocument(); // страницы
  expect(screen.getByRole("heading", { name: "Статистика" })).toBeInTheDocument();

  // карточки-итоги. Числа вроде «9» проверяем через подпись, а не getByText:
  // одни и те же цифры встречаются в разных местах страницы.
  expect(screen.getByText("Прочитано")).toBeInTheDocument();
  expect(screen.getByText("Средняя оценка")).toBeInTheDocument();
  expect(screen.getByText(/оценено книг: 1/)).toBeInTheDocument();

  // год и топы
  expect(screen.getByText(/в 2026 году — 1/)).toBeInTheDocument();
  expect(screen.getByText("Томас Манн")).toBeInTheDocument();
  expect(screen.getByText("Роман")).toBeInTheDocument();
});

test("AI-наблюдения появляются только после нажатия кнопки", async () => {
  renderApp("/stats");
  // кнопка появляется только вместе с данными — её и ждём
  const button = await screen.findByRole(
    "button", { name: "Найти закономерности" }, SLOW,
  );

  // до нажатия текста нет — токены не тратим на автозагрузке
  expect(screen.queryByText(/Летом вы читаете/)).not.toBeInTheDocument();

  await userEvent.click(button);

  expect(
    await screen.findByText("Летом вы читаете заметно больше."),
  ).toBeInTheDocument();
});

test("из библиотеки есть переход в статистику", async () => {
  renderApp();
  await screen.findByText("Волшебная гора");

  await userEvent.click(screen.getByRole("link", { name: /Статистика/ }));

  expect(
    await screen.findByRole("heading", { name: "Статистика" }, SLOW),
  ).toBeInTheDocument();
});
