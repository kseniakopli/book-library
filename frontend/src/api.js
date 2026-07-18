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

// Атмосфера: единые эндпоинты для всех категорий (music, design, food, aroma).
// GET и POST возвращают одинаковый формат: { book_id, category, selections: [...] }
export const getAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`);
export const generateAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`, { method: "POST" });
