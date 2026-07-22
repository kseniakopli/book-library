// Ключи кэша React Query (R8): одно место вместо строк по всему коду —
// опечатка в ключе означала бы молчаливо неработающую инвалидацию.
// Инвалидация по префиксу keys.books обновляет и список, и карточки книг.
export const keys = {
  books: ["books"],
  book: (id) => ["books", Number(id)],
  search: (term) => ["search", term],
  atmosphere: (id, category) => ["atmosphere", Number(id), category],
  designSummary: ["design-summary"],   // символы+палитры для символьного режима полки
  pendingCount: ["pending-count"],      // задача 56б: поллинг фонового обогащения
  recommendations: ["recommendations"], // этап 8: советы новых книг
  stats: ["stats"],                     // задачи 24/63: статистика чтения
  feedback: ["feedback"],               // задача 26: 👍/👎 по AI-подборкам
};
