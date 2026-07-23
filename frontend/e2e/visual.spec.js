// Визуальная регрессия (задача 86). Снимает эталонные скриншоты ключевых
// экранов и при следующих прогонах сравнивает пиксельно — ловит поехавшую
// вёрстку, которую функциональный smoke (з.68) не видит.
//
// Данные замоканы (visual-mocks.js), поэтому кадр детерминированный.
// НЕ в CI: скриншоты платформозависимы (шрифты рендерятся по-разному
// на Windows/Linux), эталон Windows не совпадёт с Linux в Actions.
// Локальный инструмент, как и smoke E2E.
//
// Первый запуск создаёт эталоны:  npm run test:visual -- --update-snapshots
// Последующие сравнивают:         npm run test:visual
import { test, expect } from "@playwright/test";
import { setupVisualMocks } from "./visual-mocks.js";

test.beforeEach(async ({ page }) => {
  await setupVisualMocks(page);
});

test("полка библиотеки", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Волшебная гора")).toBeVisible();
  await expect(page).toHaveScreenshot("shelf.png", { fullPage: true });
});

test("страница книги", async ({ page }) => {
  await page.goto("/books/1");
  await expect(
    page.getByRole("heading", { name: "Волшебная гора" }),
  ).toBeVisible();
  // ждём подборку музыки — значит атмосфера отрисована
  await expect(page.getByText("Spiegel im Spiegel")).toBeVisible();
  await expect(page).toHaveScreenshot("book.png", { fullPage: true });
});

test("печатная карточка A6", async ({ page }) => {
  await page.goto("/books/1/card");
  await expect(page.getByText("Волшебная гора")).toBeVisible();
  await expect(page).toHaveScreenshot("card.png", { fullPage: true });
});
