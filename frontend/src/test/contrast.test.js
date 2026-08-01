// Дотягивание цвета до читаемого контраста (аудит 28.07, находка 7).
//
// Палитру паспорта придумывает модель, и accent из неё идёт в текст (statement)
// и в фон под белыми буквами. Проверка hasReadableContrast смотрела только пару
// текст/фон, поэтому accent мог давать 3.6:1 при норме 4.5.
import { test, expect } from "vitest";
import { accentPair, contrastRatio, ensureContrast } from "../lib/contrast";

test("читаемый цвет остаётся нетронутым", () => {
  // #b45309 на #faf7f2 — 4.7:1, норму проходит
  expect(ensureContrast("#b45309", "#faf7f2")).toBe("#b45309");
});

test("тусклый акцент на светлом фоне темнеет до нормы", () => {
  // реальный случай: паспорт книги 187 дал accent #b5652f (3.6:1)
  const fixed = ensureContrast("#b5652f", "#f2eade");

  expect(fixed).not.toBe("#b5652f");
  expect(contrastRatio(fixed, "#f2eade")).toBeGreaterThanOrEqual(4.5);
});

test("на тёмном фоне цвет, наоборот, светлеет", () => {
  const bg = "#171310";
  const fixed = ensureContrast("#4a3a28", bg);

  expect(contrastRatio(fixed, bg)).toBeGreaterThanOrEqual(4.5);
  // светлее исходного: сравниваем по контрасту к чёрному
  expect(contrastRatio(fixed, "#000000")).toBeGreaterThan(
    contrastRatio("#4a3a28", "#000000"),
  );
});

test("тон и насыщенность сохраняются — меняется только светлота", () => {
  // оранжевый остаётся оранжевым: красный канал по-прежнему старший, синий младший
  const fixed = ensureContrast("#b5652f", "#f2eade");
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(fixed.slice(i, i + 2), 16));

  expect(r).toBeGreaterThan(g);
  expect(g).toBeGreaterThan(b);
});

test("не-hex цвет возвращается как есть", () => {
  expect(ensureContrast("rgb(1,2,3)", "#ffffff")).toBe("rgb(1,2,3)");
  expect(ensureContrast(undefined, "#ffffff")).toBe(undefined);
});

test("очень светлый цвет на белом тоже дотягивается", () => {
  const fixed = ensureContrast("#fff7cc", "#ffffff");

  expect(contrastRatio(fixed, "#ffffff")).toBeGreaterThanOrEqual(4.5);
});

// --- accentPair: акцент в двух ролях (аудит 01.08) ---
//
// Проверяем ОБЕ роли сразу. Прежняя проверка смотрела только «акцент как текст»,
// и страница «вечера» уезжала с текстом на кнопке 4.41:1 при норме 4.5 —
// мимо теста, потому что тест спрашивал не о том.
test("accentPair даёт AA и как текст на фоне, и как фон под буквами", () => {
  // реальный случай из отчёта аудита: акцент паспорта на светлой сцене
  const { accent, onAccent } = accentPair("#96723a", "#f2eade");

  expect(contrastRatio(accent, "#f2eade")).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(onAccent, accent)).toBeGreaterThanOrEqual(4.5);
});

test("accentPair не портит уже читаемый акцент", () => {
  const { accent } = accentPair("#7a2740", "#f4f2f0"); // 8.6:1, трогать нечего

  expect(accent).toBe("#7a2740");
});

test("accentPair работает и на тёмной сцене", () => {
  const { accent, onAccent } = accentPair("#4a3a28", "#171310");

  expect(contrastRatio(accent, "#171310")).toBeGreaterThanOrEqual(4.5);
  expect(contrastRatio(onAccent, accent)).toBeGreaterThanOrEqual(4.5);
});
