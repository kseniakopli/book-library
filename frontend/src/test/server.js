// Мок-бэкенд для фронтенд-тестов (MSW): перехватывает fetch-запросы
// и отвечает как настоящий FastAPI, но из памяти. Реальный бэкенд не нужен.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

function initialBooks() {
  return [
    {
      id: 1,
      title: "Волшебная гора",
      author: "Томас Манн",
      status: "read",
      rating: 9,
      cover_url: null,
      description: "Роман о санатории в Альпах.",
      enrich_status: "ready",
    },
    {
      id: 2,
      title: "Дом огней",
      author: "Донато Карризи",
      status: "want",
      rating: null,
      cover_url: null,
      description: null,
      enrich_status: "ready",
    },
    {
      id: 3,
      title: "Замок Броуди",
      author: "Арчибальд Кронин",
      status: "want",
      rating: null,
      cover_url: null,
      description: null,
      enrich_status: "ready",
    },
  ];
}

export const db = { books: initialBooks() };

export function resetDb() {
  db.books = initialBooks();
}

function findBook(params) {
  return db.books.find((b) => b.id === Number(params.id));
}

const notFound = () =>
  HttpResponse.json({ detail: "Книга не найдена" }, { status: 404 });

export const handlers = [
  http.get("/books", () => HttpResponse.json(db.books)),

  http.get("/books/:id", ({ params }) => {
    const book = findBook(params);
    return book ? HttpResponse.json(book) : notFound();
  }),

  http.post("/books", async ({ request }) => {
    const body = await request.json();
    const book = {
      id: 100 + db.books.length,
      title: body.title,
      author: body.author,
      status: body.status ?? "want",
      rating: null,
      read_at: body.read_at ?? null,
      cover_url: body.cover_url ?? null,
      description: null,
      enrich_status: "ready", // в тестах «фон» мгновенный — без поллинга
    };
    db.books.push(book);
    return HttpResponse.json(book);
  }),

  http.patch("/books/:id", async ({ params, request }) => {
    const book = findBook(params);
    if (!book) return notFound();
    const body = await request.json();
    Object.assign(book, body);
    if (book.status !== "read") book.rating = null;
    return HttpResponse.json(book);
  }),

  http.delete("/books/:id", ({ params }) => {
    const book = findBook(params);
    if (!book) return notFound();
    db.books = db.books.filter((b) => b.id !== book.id);
    return HttpResponse.json({ deleted: book.id });
  }),

  http.get("/search", ({ request }) => {
    const q = (new URL(request.url).searchParams.get("q") || "").toLowerCase();
    const results = q.includes("гарри")
      ? [
          {
            title: "Гарри Поттер и философский камень",
            author: "Дж. К. Роулинг",
            cover_url: null,
            external_id: "hp1",
          },
        ]
      : [];
    return HttpResponse.json({ results });
  }),

  http.post("/import", () =>
    HttpResponse.json({ imported: 2, duplicates: 1, skipped: 0 }),
  ),

  // Атмосфера: единый формат для всех категорий (music, design, ...)
  http.get("/books/:id/atmosphere/:category", ({ params }) =>
    HttpResponse.json({
      book_id: Number(params.id),
      category: params.category,
      selections: [],
    }),
  ),
  http.post("/books/:id/atmosphere/:category", ({ params }) => {
    const fixtures = {
      music: [{ title: "Song A", artist: "Artist A" }],
      food: [{ title: "Глинтвейн", description: "Тёплый и пряный" }],
      aroma: [{ title: "Сандал", description: "Дымный, тёплый" }],
    };
    return HttpResponse.json({
      book_id: Number(params.id),
      category: params.category,
      selections: ["Claude", "ChatGPT"].map((source) => ({
        source,
        payload: fixtures[params.category] ?? [],
        explanation: `${source} explanation`,
      })),
    });
  }),
];

export const server = setupServer(...handlers);
