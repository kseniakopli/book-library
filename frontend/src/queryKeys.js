// Ключи кэша React Query (R8): одно место вместо строк по всему коду —
// опечатка в ключе означала бы молчаливо неработающую инвалидацию.
// Инвалидация по префиксу keys.books обновляет и список, и карточки книг.
export const keys = {
  me: ["auth", "me"],                                       // этап 9: текущий пользователь
  showcase: (slug) => ["public", slug],                     // задача 30: витрина
  showcaseBook: (slug, id) => ["public", slug, Number(id)],
  books: ["books"],
  book: (id) => ["books", Number(id)],
  // задача 70: полка постранично; префикс "books" — общая инвалидация задевает и её
  shelf: (status) => ["books", "shelf", status],
  search: (term) => ["search", term],
  atmosphere: (id, category) => ["atmosphere", Number(id), category],
  designSummary: ["design-summary"],   // символы+палитры для символьного режима полки
  pendingCount: ["pending-count"],      // задача 56б: поллинг фонового обогащения
  recommendations: ["recommendations"], // этап 8: советы новых книг
  stats: ["stats"],                     // задачи 24/63: статистика чтения
  aiStats: ["stats", "ai"],             // задача 84: расход на AI и acceptance rate
  feedback: ["feedback"],               // задача 26: 👍/👎 по AI-подборкам
  series: ["series"],                   // задача 89: полка циклов
  seriesOne: (id) => ["series", Number(id)],
  author: (id) => ["authors", Number(id)],  // задача 97: страница автора
  authors: ["authors"],                     // задача 111: список авторов
};
