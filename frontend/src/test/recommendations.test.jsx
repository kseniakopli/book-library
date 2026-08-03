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

test("пожелания сохраняются и остаются на странице", async () => {
  // задача 114: тот же механизм, что профиль вкуса по 👍/👎, но словами
  renderApp("/recommendations");

  const field = await screen.findByLabelText(
    "Пожелания для рекомендаций", {}, SLOW,
  );
  // кнопка неактивна, пока текст не изменён — незачем слать пустое сохранение
  expect(screen.getByRole("button", { name: "Сохранить пожелания" })).toBeDisabled();

  await userEvent.type(field, "не люблю антиутопии");
  await userEvent.click(screen.getByRole("button", { name: "Сохранить пожелания" }));

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Сохранить пожелания" })).toBeDisabled(),
  );
  expect(field).toHaveValue("не люблю антиутопии");
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
