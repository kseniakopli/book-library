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
      created_at: "2026-07-01T10:00:00",
      read_at: "2026-07-10T10:00:00",
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
      created_at: "2026-07-02T10:00:00",   // добавлена раньше «Замка Броуди»
      read_at: null,
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
      created_at: "2026-07-05T10:00:00",   // добавлена позже → выше на полке
      read_at: null,
    },
  ];
}

export const db = { books: initialBooks(), recommendations: [] };

export function resetDb() {
  db.books = initialBooks();
  db.recommendations = [];
}

function findBook(params) {
  return db.books.find((b) => b.id === Number(params.id));
}

const notFound = () =>
  HttpResponse.json({ detail: "Книга не найдена" }, { status: 404 });

export const handlers = [
  http.get("/api/v1/books", () => HttpResponse.json(db.books)),

  // задача 56б: счётчик фонового обогащения (в тестах фон мгновенный)
  http.get("/api/v1/books/pending-count", () =>
    HttpResponse.json({
      pending: db.books.filter((b) => b.enrich_status === "pending").length,
    }),
  ),

  http.get("/api/v1/books/:id", ({ params }) => {
    const book = findBook(params);
    return book ? HttpResponse.json(book) : notFound();
  }),

  http.post("/api/v1/books", async ({ request }) => {
    const body = await request.json();
    const book = {
      id: 100 + db.books.length,
      title: body.title,
      author: body.author,
      status: body.status ?? "want",
      rating: null,
      read_at: body.read_at ?? null,
      created_at: new Date().toISOString(),   // только что добавлена → выше всех
      cover_url: body.cover_url ?? null,
      description: null,
      enrich_status: "ready", // в тестах «фон» мгновенный — без поллинга
    };
    db.books.push(book);
    return HttpResponse.json(book);
  }),

  http.patch("/api/v1/books/:id", async ({ params, request }) => {
    const book = findBook(params);
    if (!book) return notFound();
    const body = await request.json();
    Object.assign(book, body);
    if (book.status !== "read") book.rating = null;
    return HttpResponse.json(book);
  }),

  http.delete("/api/v1/books/:id", ({ params }) => {
    const book = findBook(params);
    if (!book) return notFound();
    db.books = db.books.filter((b) => b.id !== book.id);
    return HttpResponse.json({ deleted: book.id });
  }),

  http.get("/api/v1/search", ({ request }) => {
    const q = (new URL(request.url).searchParams.get("q") || "").toLowerCase();
    let results = [];
    if (q.includes("гарри")) {
      results = [
        {
          title: "Гарри Поттер и философский камень",
          author: "Дж. К. Роулинг",
          cover_url: null,
          external_id: "hp1",
          book_id: null,
          source: "google",
          on_shelf: false,
        },
      ];
    } else if (q.includes("манн")) {
      // локальный каталог: книга уже в системе и на полке пользователя
      results = [
        {
          title: "Волшебная гора",
          author: "Томас Манн",
          cover_url: null,
          external_id: null,
          book_id: 1,
          source: "library",
          on_shelf: true,
        },
      ];
    }
    return HttpResponse.json({ results });
  }),

  http.post("/api/v1/import", () =>
    HttpResponse.json({ imported: 2, duplicates: 1, skipped: 0 }),
  ),

  // Рекомендации (этап 8): пусто до генерации, POST наполняет набор
  http.get("/api/v1/recommendations", () =>
    HttpResponse.json({ recommendations: db.recommendations }),
  ),
  http.post("/api/v1/recommendations", () => {
    // с 20.07 советуют обе модели — у каждой карточки есть источник
    db.recommendations = [
      {
        title: "Тень ветра",
        author: "Карлос Руис Сафон",
        reason: "Готическая тайна в духе «Волшебной горы», которую вы оценили высоко",
        source: "Claude",
        cover_url: null,
        external_id: null,
      },
      {
        title: "Имя розы",
        author: "Умберто Эко",
        reason: "Медленный детектив в монастыре — под ваш вкус к атмосфере",
        source: "ChatGPT",
        cover_url: null,
        external_id: null,
      },
    ];
    return HttpResponse.json({ recommendations: db.recommendations });
  }),

  // Статистика (задачи 24/63): готовые цифры с бэкенда
  http.get("/api/v1/stats", () =>
    HttpResponse.json({
      totals: { all: 3, read: 1, reading: 0, want: 2 },
      pages_read: 706,
      average_rating: 9.0,
      rated_count: 1,
      ratings: Array.from({ length: 10 }, (_, i) => ({
        rating: i + 1,
        count: i + 1 === 9 ? 1 : 0,
      })),
      by_month: [
        { month: "2025-08", count: 0 },
        { month: "2026-07", count: 1 },
      ],
      this_year: { year: 2026, count: 1 },
      streak_months: 1,
      top_authors: [{ author: "Томас Манн", count: 1 }],
      top_genres: [{ genre: "Роман", count: 1 }],
    }),
  ),
  http.post("/api/v1/stats/insights", () =>
    HttpResponse.json({
      observations: ["Летом вы читаете заметно больше."],
    }),
  ),

  // Символьный режим полки (задача 66): символ+палитры паспорта по книгам
  http.get("/api/v1/books/design-summary", () =>
    HttpResponse.json({
      designs: [
        {
          book_id: 1,
          symbol_svg: '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>',
          palette_dark: {
            bg: "#161311", surface: "#221c17", accent: "#e08b2d",
            text: "#e9e1d3", muted: "#a19585",
          },
          palette_light: {
            bg: "#f6f1e7", surface: "#fffaf0", accent: "#b05e12",
            text: "#2a241d", muted: "#6d655b",
          },
        },
      ],
    }),
  ),

  // Атмосфера: единый формат для всех категорий (music, design, ...)
  http.get("/api/v1/books/:id/atmosphere/:category", ({ params }) =>
    HttpResponse.json({
      book_id: Number(params.id),
      category: params.category,
      selections: [],
    }),
  ),
  http.post("/api/v1/books/:id/atmosphere/:category", ({ params }) => {
    // Паспорт оформления (задача 57): один источник, объект с двумя палитрами.
    // symbol_svg намеренно нет — jsdom не умеет getBBox из centeredSvgDataUri.
    if (params.category === "design") {
      return HttpResponse.json({
        book_id: Number(params.id),
        category: "design",
        selections: [
          {
            source: "Claude",
            payload: {
              base_mood: "тестовая ночь",
              palette_dark: {
                bg: "#161311", surface: "#221c17", accent: "#e08b2d",
                text: "#e9e1d3", muted: "#a19585",
              },
              palette_light: {
                bg: "#f6f1e7", surface: "#fffaf0", accent: "#b05e12",
                text: "#2a241d", muted: "#6d655b",
              },
              title_font: "PT Serif",
              body_font: "PT Serif",
              statement: "Символ выбран для теста",
            },
            explanation: "Символ выбран для теста",
          },
        ],
      });
    }
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
