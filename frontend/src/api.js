// Единый слой запросов к бэкенду. Бросает ошибку при не-2xx —
// React Query превратит её в isError у запроса/мутации.

// Задача 34: версионированный префикс. Экспортируется для не-fetch мест
// (например, src у QR-картинки на печатной карточке).
export const API = "/api/v1";

async function request(url, options) {
  const response = await fetch(`${API}${url}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail || `Ошибка ${response.status}`);
    // этап 9: код нужен, чтобы отличить «не вошёл» (401) от настоящей поломки —
    // по 401 приложение показывает страницу входа, а не сообщение об ошибке
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// Авторизация (этап 9). Сессия — в httpOnly-куке, поэтому токен здесь нигде
// не хранится и не передаётся: браузер сам приложит куку к запросу.
export const getMe = () => request("/auth/me");
export const getAuthStatus = () => request("/auth/status");
export const logout = () => request("/auth/logout", { method: "POST" });
// Вход — не fetch, а переход браузера: дальше нас ведёт Google
export const loginUrl = (invite) =>
  `${API}/auth/google/login?invite=${encodeURIComponent(invite || "")}`;

// Публичная витрина (задача 30) — единственные запросы, работающие без входа
export const getShowcase = (slug) => request(`/public/${slug}`);
export const getShowcaseBook = (slug, id) => request(`/public/${slug}/books/${id}`);

export const getBooks = () => request("/books");
// Задача 70: полка постранично. total приходит заголовком X-Total-Count,
// поэтому единый request() не подходит — нужен доступ к заголовкам ответа.
export const getShelf = async ({ status, offset = 0, limit = 30 }) => {
  const params = new URLSearchParams({ status, offset, limit });
  const response = await fetch(`${API}/books?${params}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка ${response.status}`);
  }
  return {
    items: await response.json(),
    total: Number(response.headers.get("X-Total-Count") ?? 0),
  };
};
// Задача 56б: лёгкий счётчик для поллинга фонового обогащения
export const getPendingCount = () => request("/books/pending-count");
export const getBook = (id) => request(`/books/${id}`);
// Задача 97: страница автора — книги с полки + книги того же автора из каталога
export const getAuthor = (id) => request(`/authors/${id}`);
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
// Задача 84: расход на AI и acceptance rate подборок. Только admin —
// у обычного пользователя эндпоинт отвечает 403, и блок просто не рисуется.
export const getAiStats = () => request("/stats/ai");
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
// Точечное удаление трека (admin): бэкенд обновит и Spotify-плейлист
export const removeTrack = ({ id, source, title, artist }) =>
  request(`/books/${id}/atmosphere/music/tracks`, json("DELETE", { source, title, artist }));
