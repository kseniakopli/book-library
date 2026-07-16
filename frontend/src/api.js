// Единый слой запросов к бэкенду. Бросает ошибку при не-2xx —
// React Query превратит её в isError у запроса/мутации.
async function request(url, options) {
  const response = await fetch(url, options);
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
export const createBook = ({ title, author, cover_url, external_id }) =>
  request("/books", json("POST", { title, author, cover_url, external_id }));
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

// Атмосфера: единые эндпоинты для всех категорий (music, design; этап 7 добавит свои).
// GET и POST возвращают одинаковый формат: { book_id, category, selections: [...] }
export const getAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`);
export const generateAtmosphere = (id, category) =>
  request(`/books/${id}/atmosphere/${category}`, { method: "POST" });
