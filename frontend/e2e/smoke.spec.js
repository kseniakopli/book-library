// Сквозной smoke (задача 68): добавить книгу вручную → открыть → печатная
// карточка → удалить. Ловит разрывы между экранами, которые юнит-тесты не видят
// (как кейс задачи 58 «книгу не найти — добавить нельзя»).
//
// Сознательно НЕ жмём «Подобрать атмосферу» — чтобы не тратить AI-токены на
// каждый прогон. Добавление книги фоном дёргает генерацию оформления один раз
// (дёшево); поиск по «щщщ…» гарантированно пуст → уходим в ручное добавление.
import { test, expect } from "@playwright/test";

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
