// Сквозной smoke (задача 68): добавить книгу вручную → открыть → печатная
// карточка → удалить. Ловит разрывы между экранами, которые юнит-тесты не видят
// (как кейс задачи 58 «книгу не найти — добавить нельзя»).
//
// Сознательно НЕ жмём «Подобрать атмосферу» — чтобы не тратить AI-токены на
// каждый прогон. Добавление книги фоном дёргает генерацию оформления один раз
// (дёшево); поиск по «щщщ…» гарантированно пуст → уходим в ручное добавление.
import { test, expect } from "@playwright/test";

// Этап 9: сервис закрыт авторизацией, а пройти согласие Google скриптом нельзя.
// Поэтому перед каждым тестом входим служебным эндпоинтом — он существует,
// только если бэкенд запущен с ALLOW_DEV_LOGIN=1:
//   cd backend; $env:ALLOW_DEV_LOGIN="1"; uvicorn main:app
test.beforeEach(async ({ page }) => {
  const response = await page.request.post("/api/v1/auth/dev-login");
  if (!response.ok()) {
    throw new Error(
      "Служебный вход недоступен. Запустите бэкенд с ALLOW_DEV_LOGIN=1 — " +
        "иначе e2e упрутся в страницу входа.",
    );
  }
});

test("добавить → открыть → печатная карточка → удалить", async ({ page }) => {
  const title = `E2E книга ${Date.now()}`; // уникальное имя, чтобы не ловить дубль-409
  const author = "E2E Автор";

  // нативный confirm при удалении — соглашаемся
  page.on("dialog", (d) => d.accept());

  await page.goto("/");

  // 1) добавление вручную (каталог такую книгу не знает)
  await page.getByRole("button", { name: "+ Добавить книгу" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByPlaceholder("Название или автор…")
    .fill("щщщ несуществующая книга щщщ");
  await dialog.getByRole("button", { name: "Добавить вручную" }).click();
  await dialog.getByLabel("Название").fill(title);
  await dialog.getByLabel("Автор").fill(author);
  await dialog.getByRole("button", { name: "Добавить" }).click();

  // 2) книга появилась в библиотеке
  await expect(page.getByText(title)).toBeVisible();

  // 3) открыть страницу книги
  await page.getByText(title).click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  // 4) печатная карточка открывается
  await page.getByRole("link", { name: "Печатная карточка" }).click();
  await expect(page).toHaveURL(/\/card$/);
  await page.goBack();

  // 5) удалить и вернуться в библиотеку — книги больше нет
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.getByRole("button", { name: "Удалить" }).click();
  await expect(page.getByText(title)).toHaveCount(0);
});


// --- Авторизация (R6, 26.07) ---
// Оба сценария ниже закрывают класс багов, который прошёл мимо юнит-тестов:
// бэкенд отвечает верно, а экран не перерисовывается под новое состояние.

test("гость видит вход и не видит библиотеку", async ({ page, context }) => {
  await context.clearCookies();            // сбрасываем служебный вход
  await page.goto("/");

  await expect(
    page.getByRole("link", { name: "Войти через Google" }),
  ).toBeVisible();
  // ни полок, ни кнопки добавления
  await expect(page.getByRole("button", { name: "+ Добавить книгу" })).toHaveCount(0);

  // прямая ссылка на книгу тоже ведёт на вход, а не отдаёт данные
  await page.goto("/books/1");
  await expect(
    page.getByRole("link", { name: "Войти через Google" }),
  ).toBeVisible();
});

test("выход возвращает на страницу входа", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "+ Добавить книгу" })).toBeVisible();

  await page.getByRole("button", { name: "Выйти" }).click();

  // баг 26.07: кнопка исчезала, а библиотека оставалась на экране
  await expect(
    page.getByRole("link", { name: "Войти через Google" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "+ Добавить книгу" })).toHaveCount(0);
});
