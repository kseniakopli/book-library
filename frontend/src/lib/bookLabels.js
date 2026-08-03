// Подписи книги: автор и строка состояния на полке.
//
// Живут в `lib/`, а не рядом с компонентами: файл компонента должен
// экспортировать ТОЛЬКО компонент, иначе Vite теряет Fast Refresh
// (oxlint: react/only-export-components). Из-за этого `shelfNote` уехал
// сюда из `BookTile.jsx` сразу после ревью 03.08.

const STATUS_LABEL = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

/** Как показывать автора книги (правка 03.08).
 *
 *  У книги два источника имени, и они не равнозначны:
 *    `book.author`  — строка каталога, написание как в источнике данных.
 *                     У «Ann Patchett» и «Joan Didion» это латиница.
 *    `book.authors` — сущности-авторы (з.97). У них есть `name_ru`, и бэкенд
 *                     отдаёт уже разрешённое имя (`display_name`).
 *
 *  По умолчанию показываем русское — то есть сущность. Строка остаётся
 *  запасным вариантом для книг, заведённых до появления таблицы авторов:
 *  у них список пуст, и терять имя из-за этого нельзя.
 *
 *  ⚠ Соавторы перечисляются через запятую в порядке обложки (`position`),
 *  который бэкенд сохраняет специально. */
export function authorLabel(book) {
  const names = (book?.authors ?? []).map((a) => a.name).filter(Boolean);
  return names.length ? names.join(", ") : (book?.author ?? "");
}

/** Подпись для книги с полки: статус и, если есть, личная оценка. */
export function shelfNote(book) {
  const status = STATUS_LABEL[book.status] ?? "";
  return book.rating ? `${status} · ★ ${book.rating}/10` : status;
}
