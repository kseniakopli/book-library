// Единый слой запросов к бэкенду. Бросает ошибку при не-2xx —
// React Query превратит её в isError у запроса/мутации.

// Задача 34: версионированный префикс. Экспортируется для не-fetch мест
// (например, src у QR-картинки на печатной карточке).
export const API = "/api/v1";

async function request(url, options) {
  const response = await fetch(`${API}${url}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка ${response.status}`);
  }
  return response.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getBooks = () => request("/books");
// Задача 56б: лёгкий счётчик для поллинга фонового обогащения
export const getPendingCount = () => request("/books/pending-count");
export const getBook = (id) => request(`/books/${id}`);
// Символьный режим полки (задача 66): символ+палитры паспорта для всех книг разом
export const getDesignSummary = () => request("/books/design-summary");
export const createBook = ({
  title,
  author,
  cover_url,
  external_id,
  book_id, // выбор книги из локального каталога — переиспользуем её (без регенерации)
  status,
  read_at,
}) =>
  request(
    "/books",
    json("POST", {
      title,
      author,
      cover_url,
      external_id,
      book_id,
      status,
      read_at,
    }),
  );
export const patchBook = ({ id, ...body }) =>
  request(`/books/${id}`, json("PATCH", body));
export const deleteBook = (id) => request(`/books/${id}`, { method: "DELETE" });
export const searchBooks = (q) => request(`/search?q=${encodeURIComponent(q)}`);
export const importCsv = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return request("/import", { method: "POST", body: formData });
};
export const enrichBook = (id) =>
  request(`/books/${id}/enrich`, { method: "POST" });
export const createPlaylist = (id) =>
  request(`/books/${id}/playlist`, { method: "POST" });

// Рекомендации (этап 8): читаются всегда, генерируются по кнопке (тратит токены)
export const getRecommendations = () => request("/recommendations");
export const generateRecommendations = () =>
  request("/recommendations", { method: "POST" });

// Статистика (задачи 24/63): цифры считает бэкенд, инсайты — по кнопке (токены)
export const getStats = () => request("/stats");
export const generateInsights = () =>
  request("/stats/insights", { method: "POST" });

// Циклы книг (задача 89): полка циклов, страница цикла, привязка книг
export const getSeries = () => request("/series");
export const getSeriesOne = (id) => request(`/series/${id}`);
export const createSeries = (body) => request("/series", json("POST", body));
export const updateSeries = ({ id, ...body }) =>
  request(`/series/${id}`, json("PATCH", body));
export const deleteSeries = (id) =>
  request(`/series/${id}`, { method: "DELETE" });
// book_id — привязать существующую; title/author — завести будущую книгу цикла
export const addBookToSeries = ({ id, ...body }) =>
  request(`/series/${id}/books`, json("POST", body));
export const removeBookFromSeries = ({ id, bookId }) =>
  request(`/series/${id}/books/${bookId}`, { method: "DELETE" });
// экслибрис цикла: генерируется по названию и описанию (тратит токены)
export const generateSeriesDesign = (id) =>
  request(`/series/${id}/design`, { method: "POST" });

// Обратная связь по AI-подборкам (задача 26): 👍/👎 на атмосферу и советы
export const getFeedback = () => request("/feedback");
export const setFeedback = ({ ref, verdict, source }) =>
  request("/feedback", json("POST", { ref, verdict, source }));

// Атмосфера: единые эндпоинты для всех категорий (music, design, food, aroma).
// GET и POST возвращают одинаковый формат: { book_id, category, selections: [...] }
export const getAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`);
export const generateAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`, { method: "POST" });
