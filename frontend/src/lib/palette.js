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

export function pickPalette(design, theme) {
  if (!design) return null;
  const dark = design.palette_dark ?? design.palette ?? null;
  const light = design.palette_light ?? null;
  // нужной палитры может не быть (старый паспорт) — берём вторую, чем ничего
  return theme === "dark" ? (dark ?? light) : (light ?? dark);
}
