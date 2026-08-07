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
// состояние мок-бэкенда: настройки проверяем по нему, а не по экрану —
// экран показывал выбор и тогда, когда до сервера тот не доезжал
import { db } from "./server";

// страница за React.lazy — первый рендер ждёт загрузки чанка
const SLOW = { timeout: 5000 };

test("до генерации страница зовёт подобрать рекомендации", async () => {
  renderApp("/recommendations");

  expect(
    await screen.findByText(/Нажмите «Подобрать рекомендации»/, {}, SLOW),
  ).toBeInTheDocument();
});

test("настройки подбора сохраняются САМИ, без кнопки", async () => {
  // ⚠ Ради этого правка 06.08. Раньше здесь был черновик и кнопка
  // «Сохранить настройки»: Ксения отметила жанры, нажала «Обновить» —
  // и получила подбор по старым настройкам (`genre_asked: 0` в событии).
  // Проверяем не экран, а ДОЕХАЛО ЛИ до сервера: экран показывал
  // выбор и в сломанном варианте (урок 3.1).
  renderApp("/recommendations");

  // ждём СПИСКИ ЖАНРОВ, а не чекбокс: чекбокс рисуется до ответа сервера
  await screen.findByText("Какие жанры рекомендовать", {}, SLOW);
  expect(
    screen.queryByRole("button", { name: /Сохранить настройки/ }),
  ).toBeNull();

  await userEvent.click(
    screen.getByRole("checkbox", { name: /Не рекомендовать авторов/ }),
  );

  await waitFor(
    () => expect(db.recSettings.skip_known_authors).toBe(true),
    { timeout: 3000 },
  );
});

test("выбор нескольких жанров подряд уходит одним запросом", async () => {
  // Задержка перед отправкой нужна, чтобы пять кликов не дали пять
  // запросов. Проверяем, что она не теряет промежуточные правки:
  // в итоге на сервере должны оказаться ОБА жанра.
  renderApp("/recommendations");
  await screen.findByText("Какие жанры рекомендовать", {}, SLOW);

  const wanted = within(
    screen.getByText("Какие жанры рекомендовать").closest(".rec-picker"),
  );
  await userEvent.click(wanted.getByRole("button", { name: "Детектив" }));
  await userEvent.click(wanted.getByRole("button", { name: "Магический реализм" }));

  await waitFor(
    () =>
      expect(db.recSettings.genres_include).toEqual([
        "детектив",
        "магический реализм",
      ]),
    { timeout: 3000 },
  );
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
