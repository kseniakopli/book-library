// Выбор палитры (lib/palette.js).
//
// pickPaletteForSymbol появилась 28.07: модель рисует ОДИН символ на две
// палитры, а каким цветом — не оговорено. У «Царствия мне небесного» крест
// нарисован светлым и на светлой витрине исчезал — оставалась одна точка.
import { test, expect } from "vitest";
import { pickPalette, pickPaletteForSymbol, symbolInk } from "../lib/palette";

const LIGHT = { bg: "#f2eade", text: "#2c2621", accent: "#b5652f" };
const DARK = { bg: "#171310", text: "#e9e1d3", accent: "#e08b2d" };

const withSymbol = (svg) => ({
  palette_light: LIGHT,
  palette_dark: DARK,
  symbol_svg: svg,
});

test("чернила символа вычитываются из fill и stroke, дубли схлопываются", () => {
  const svg =
    '<svg><rect fill="#1D2333"/><path stroke="#d98b3f"/><line stroke="#1d2333"/></svg>';
  expect(symbolInk(svg)).toEqual(["#1d2333", "#d98b3f"]);
});

test("none и currentColor чернилами не считаются", () => {
  const svg = '<svg><path fill="none" stroke="currentColor" d="M0 0"/></svg>';
  expect(symbolInk(svg)).toEqual([]);
});

test("светлый символ уходит на тёмный фон", () => {
  const design = withSymbol('<svg><path stroke="#e9e1d3" d="M50 20v60"/></svg>');
  expect(pickPaletteForSymbol(design).bg).toBe(DARK.bg);
});

test("тёмный символ остаётся на светлом фоне", () => {
  const design = withSymbol(
    '<svg><rect fill="#1d2333"/><path fill="#d98b3f"/></svg>',
  );
  expect(pickPaletteForSymbol(design).bg).toBe(LIGHT.bg);
});

test("решает САМЫЙ бледный штрих, а не первый попавшийся", () => {
  // тёмный контур виден везде, а светлая заливка — только на тёмном фоне
  const design = withSymbol(
    '<svg><path stroke="#1d2333"/><circle fill="#f0e6d8"/></svg>',
  );
  expect(pickPaletteForSymbol(design).bg).toBe(DARK.bg);
});

test("символ без явных цветов — светлая палитра по умолчанию", () => {
  expect(pickPaletteForSymbol(withSymbol("<svg><path d='M0 0'/></svg>")).bg).toBe(
    LIGHT.bg,
  );
});

test("старый паспорт с одной палитрой: берём что есть", () => {
  const old = { palette: DARK, symbol_svg: '<svg><path fill="#fff"/></svg>' };
  expect(pickPaletteForSymbol(old).bg).toBe(DARK.bg);
  expect(pickPaletteForSymbol(null)).toBe(null);
});

test("pickPalette по-прежнему выбирает по теме интерфейса", () => {
  const design = { palette_light: LIGHT, palette_dark: DARK };
  expect(pickPalette(design, "dark").bg).toBe(DARK.bg);
  expect(pickPalette(design, "light").bg).toBe(LIGHT.bg);
});
