// Единое правило выбора палитры паспорта под тему интерфейса.
//
// Зачем отдельный модуль: раньше это правило было написано в трёх местах
// (BookDetail, BookCard, EveningPage) и успело разъехаться — по-разному
// обрабатывались старый формат паспорта и пропущенная палитра, из-за чего одна
// книга могла выглядеть по-разному на полке, на своей странице и в «вечере».
//
// Форматы паспорта:
//   новый  — palette_dark + palette_light;
//   старый — одно поле palette (оно тёмное).

import { contrastRatio } from "./contrast";

export function pickPalette(design, theme) {
  if (!design) return null;
  const dark = design.palette_dark ?? design.palette ?? null;
  const light = design.palette_light ?? null;
  // нужной палитры может не быть (старый паспорт) — берём вторую, чем ничего
  return theme === "dark" ? (dark ?? light) : (light ?? dark);
}

// Цвета, которыми нарисован символ: явные fill/stroke в разметке SVG.
// `none`/`transparent`/`currentColor` не в счёт — они ничего не закрашивают.
const INK_RE = /(?:fill|stroke)\s*[:=]\s*["']?\s*(#[0-9a-fA-F]{3,8})/g;

export function symbolInk(svg) {
  if (typeof svg !== "string") return [];
  return [...new Set(Array.from(svg.matchAll(INK_RE), (m) => m[1].toLowerCase()))];
}

/**
 * Палитра для ПЛАШКИ С СИМВОЛОМ — по контрасту с самим символом, а не по теме.
 *
 * Зачем (28.07): модель рисует один символ на две палитры и цвета берёт «из
 * паспорта», но какой именно палитры — не оговорено. У «Царствия мне небесного»
 * крест нарисован светлым: на тёмном фоне он виден, на светлом исчезает, и
 * в витрине карточка выглядела пустой — только точка посередине.
 *
 * Поэтому фон плашки выбираем тот, на котором виден САМЫЙ незаметный элемент
 * символа: считаем минимальный контраст чернил к каждому из двух фонов и берём
 * лучший. Символ без явных цветов (наследует currentColor) — оставляем светлую.
 */
export function pickPaletteForSymbol(design) {
  if (!design) return null;
  const dark = design.palette_dark ?? design.palette ?? null;
  const light = design.palette_light ?? null;
  if (!dark || !light) return light ?? dark;

  const inks = symbolInk(design.symbol_svg);
  if (!inks.length) return light;

  // худший элемент решает: символ читается настолько, насколько виден его
  // самый бледный штрих
  const worst = (palette) =>
    Math.min(...inks.map((ink) => contrastRatio(ink, palette.bg) ?? 1));

  return worst(light) >= worst(dark) ? light : dark;
}
