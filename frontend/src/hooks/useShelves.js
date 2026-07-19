// Разбор библиотеки по полкам с сортировкой (ревью 19.07 — вынесено из HomePage).
//
// «Читаю» — недавно начатые (updated_at ↓; отдельного started_at пока нет, он в задаче 27);
// «Прочитано» — недавно прочитанные (read_at ↓);
// «Хочу прочитать» — недавно добавленные (created_at = когда книга легла на полку).
//
// filter() возвращает новый массив, поэтому sort() не мутирует кэш React Query.
import { useMemo } from "react";

// по дате (ISO-строка) убыванию; книги без даты уходят в конец
const byDateDesc = (field) => (a, b) =>
  (b[field] ?? "").localeCompare(a[field] ?? "");

export function useShelves(books) {
  return useMemo(
    () => ({
      reading: books
        .filter((b) => b.status === "reading")
        .sort(byDateDesc("updated_at")),
      read: books
        .filter((b) => b.status === "read")
        .sort(byDateDesc("read_at")),
      want: books
        .filter((b) => b.status === "want")
        .sort(byDateDesc("created_at")),
    }),
    [books],
  );
}
