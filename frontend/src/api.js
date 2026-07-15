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
export const createBook = ({ title, author }) =>
  request("/books", json("POST", { title, author }));
export const patchBook = ({ id, ...body }) =>
  request(`/books/${id}`, json("PATCH", body));
export const deleteBook = (id) => request(`/books/${id}`, { method: "DELETE" });
export const searchBooks = (q) => request(`/search?q=${encodeURIComponent(q)}`);
export const importCsv = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return request("/import", { method: "POST", body: formData });
};
export const getMusic = (id) => request(`/books/${id}/music`);
export const generateMusic = (id) =>
  request(`/books/${id}/music`, { method: "POST" });
export const getDesign = (id) => request(`/books/${id}/design`);
export const generateDesign = (id) =>
  request(`/books/${id}/design`, { method: "POST" });
export const enrichBook = (id) =>
  request(`/books/${id}/enrich`, { method: "POST" });
