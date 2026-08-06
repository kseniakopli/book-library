// Рекомендации (этап 8) на своей странице (задача 110): подбор по кнопке
// и добавление совета в библиотеку.
//
// ⚠ С задачи 110 полка живёт НЕ на главной, а на /recommendations — попасть
// туда можно через меню ЛК. Тесты открывают страницу напрямую; сам путь через
// меню проверяется в menu.test.jsx.
import { test, expect } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "./utils";

// страница за React.lazy — первый рендер ждёт загрузки чанка
const SLOW = { timeout: 5000 };

test("до генерации страница зовёт подобрать рекомендации", async () => {
  renderApp("/recommendations");

  expect(
    await screen.findByText(/Нажмите «Подобрать рекомендации»/, {}, SLOW),
  ).toBeInTheDocument();
});

test("настройки подбора сохраняются и остаются на странице", async () => {
  // Задача 124: пожелания СЛОВАМИ (з.114) заменены настройками —
  // свободный текст было непонятно, как исполнять.
  renderApp("/recommendations");

  // ⚠ Ждём СПИСКИ ЖАНРОВ, а не чекбокс: чекбокс рисуется сразу, ещё до
  // ответа сервера, и клик по нему в этот момент затирался бы пришедшими
  // настройками. Появление жанров означает, что данные уже здесь.
  await screen.findByText("Какие жанры рекомендовать", {}, SLOW);
  const checkbox = screen.getByRole("checkbox", {
    name: /Не рекомендовать авторов/,
  });
  const save = () => screen.getByRole("button", { name: "Сохранить настройки" });
  // кнопка неактивна, пока ничего не меняли — незачем слать пустое сохранение
  expect(save()).toBeDisabled();

  await userEvent.click(checkbox);
  await userEvent.click(save());

  await waitFor(() => expect(save()).toBeDisabled());
  expect(checkbox).toBeChecked();
});

test("правка не теряется, если кликнуть до загрузки настроек", async () => {
  // Гонка, найденная тестом 06.08: чекбокс рисуется сразу, ответ сервера
  // приходит позже, и `useEffect` затирал им черновик — галочка молча
  // слетала. Здесь кликаем ДО появления списков, то есть до ответа.
  renderApp("/recommendations");

  const checkbox = await screen.findByRole(
    "checkbox", { name: /Не рекомендовать авторов/ }, SLOW,
  );
  await userEvent.click(checkbox);

  // теперь дожидаемся данных — и проверяем, что клик пережил их приход
  await screen.findByText("Какие жанры рекомендовать", {}, SLOW);
  expect(checkbox).toBeChecked();
});

test("жанр нельзя выбрать сразу в оба списка", async () => {
  // «Хочу детективы» и «не хочу детективы» одновременно — это не выбор,
  // а противоречие: вторая кнопка гасится.
  renderApp("/recommendations");
  await screen.findByText("Какие жанры рекомендовать", {}, SLOW);

  const wanted = within(
    screen.getByText("Какие жанры рекомендовать").closest(".rec-picker"),
  );
  const unwanted = within(
    screen.getByText("Какие жанры не рекомендовать").closest(".rec-picker"),
  );

  await userEvent.click(wanted.getByRole("button", { name: "Детектив" }));

  expect(wanted.getByRole("button", { name: "Детектив" })).toHaveAttribute(
    "aria-pressed", "true",
  );
  expect(unwanted.getByRole("button", { name: "Детектив" })).toBeDisabled();
  // соседний жанр при этом доступен — гасится именно выбранный
  expect(unwanted.getByRole("button", { name: "Магический реализм" })).toBeEnabled();
});

test("рекомендации подбираются по кнопке и добавляются в «Хочу прочитать»", async () => {
  renderApp("/recommendations");

  await userEvent.click(
    await screen.findByRole("button", { name: "Подобрать рекомендации" }, SLOW),
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

  // и книга действительно легла на полку — проверяем на главной, потому что
  // полок на странице рекомендаций больше нет
  await userEvent.click(screen.getByRole("link", { name: /К библиотеке/ }));
  await waitFor(() =>
    expect(screen.getByText("Тень ветра")).toBeInTheDocument(),
  );
});
