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
      // Задача 97: авторы-сущности. С 03.08 приходят и в СПИСКЕ полки:
      // строка каталога хранит написание как в источнике, а показывать надо
      // русское имя (у «Ann Patchett» они различаются).
      authors: [{ id: 7, name: "Томас Манн" }],
      on_shelf: true,
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

export const db = {
  books: initialBooks(),
  recommendations: [],
  feedback: {},
  authorBio: null,   // задача 111: биография правится на месте
  // задача 124: настройки подбора (пришли на смену пожеланиям словами)
  recSettings: { skip_known_authors: false, genres_include: [], genres_exclude: [] },
};

export function resetDb() {
  db.books = initialBooks();
  db.recommendations = [];
  db.feedback = {};
  db.authorBio = null;
  db.recSettings = { skip_known_authors: false, genres_include: [], genres_exclude: [] };
}

function findBook(params) {
  return db.books.find((b) => b.id === Number(params.id));
}

const notFound = () =>
  HttpResponse.json({ detail: "Книга не найдена" }, { status: 404 });

// Задача 70: сортировка полок как на бэкенде (SHELF_ORDER в routers/books.py)
const SHELF_SORT = { read: "read_at", want: "created_at", reading: "updated_at" };

export const handlers = [
  // Этап 9: в тестах пользователь всегда «вошёл» и он админ — иначе App
  // показал бы страницу входа вместо библиотеки. Тест на гостя подменяет
  // этот хэндлер (server.use) и получает 401.
  http.get("/api/v1/auth/me", () =>
    HttpResponse.json({
      id: 1,
      display_name: "Ксения",
      email: "owner@example.com",
      avatar_url: null,
      is_admin: true,
    }),
  ),
  // Задача 30: публичная витрина (гостевые страницы)
  http.get("/api/v1/public/:slug", ({ params }) =>
    HttpResponse.json({
      title: `Библиотека: ${params.slug}`,
      intro: "Отобранные книги",
      books: [{
        id: 1, title: "Волшебная гора", author: "Томас Манн", cover_url: null,
        // паспорт со светлым символом: на витрине плашка должна уйти в тёмную
        // палитру, иначе символ не виден (28.07)
        design: {
          base_mood: "туманная меланхолия",
          symbol_svg: '<svg viewBox="0 0 100 100"><path stroke="#e9e1d3" d="M50 20v60"/></svg>',
          palette_light: { bg: "#f2eade", text: "#2c2621", accent: "#b5652f" },
          palette_dark: { bg: "#171310", text: "#e9e1d3", accent: "#e08b2d" },
        },
      }],
    }),
  ),
  http.get("/api/v1/public/:slug/books/:id", () =>
    HttpResponse.json({
      id: 1, title: "Волшебная гора", author: "Томас Манн", cover_url: null,
      description: "Роман о санатории в Альпах.", published_year: 1924,
      spotify_playlist_url: null, design: null,
      atmosphere: { music: { items: [{ title: "Song A", artist: "Artist A" }],
                             explanation: "Тихо" } },
      showcase_title: "Библиотека",
    }),
  ),

  http.get("/api/v1/auth/status", () =>
    HttpResponse.json({ oauth_configured: true }),
  ),
  http.post("/api/v1/auth/logout", () => HttpResponse.json({ ok: true })),

  // Задача 70: /books понимает status/limit/offset, сортирует полку и отдаёт
  // общее число заголовком X-Total-Count — как настоящий бэкенд
  http.get("/api/v1/books", ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const limit = url.searchParams.get("limit");

    let items = status
      ? db.books.filter((b) => b.status === status)
      : [...db.books];
    const field = SHELF_SORT[status];
    if (field) {
      items = [...items].sort((a, b) =>
        (b[field] ?? "").localeCompare(a[field] ?? ""),
      );
    }
    const total = items.length;
    items = items.slice(
      offset,
      limit != null ? offset + Number(limit) : undefined,
    );
    return HttpResponse.json(items, {
      headers: { "X-Total-Count": String(total) },
    });
  }),

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

  // задача 97: страница автора — две стопки, полка и каталог
  // задача 111: bio редактируется на месте, поэтому живёт в изменяемом db
  http.get("/api/v1/authors/:id", ({ params }) =>
    Number(params.id) === 7
      ? HttpResponse.json({
          id: 7,
          name: "Томас Манн",
          name_ru: "Томас Манн",
          name_original: null,
          bio: db.authorBio,
          shelf: [
            {
              id: 1,
              title: "Волшебная гора",
              status: "read",
              rating: 9,
              cover_url: null,
              published_year: 1924,
            },
          ],
          catalog: [
            {
              id: 42,
              title: "Будденброки",
              cover_url: null,
              series_index: null,
              published_year: 1901,
            },
          ],
        })
      : notFound(),
  ),
  http.patch("/api/v1/authors/:id", async ({ request }) => {
    const body = await request.json();
    db.authorBio = (body.bio ?? "").trim() || null;
    return HttpResponse.json({ id: 7, bio: db.authorBio });
  }),

  // Задача 123: книга заводится в КАТАЛОГЕ автора, не на полке.
  // Отвечаем свежей карточкой — фронт кладёт её в кэш вместо второго запроса.
  http.post("/api/v1/authors/:id/books", async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(
      {
        id: 7,
        name: "Томас Манн",
        name_ru: "Томас Манн",
        name_original: null,
        bio: db.authorBio,
        shelf: [
          {
            id: 1,
            title: "Волшебная гора",
            status: "read",
            rating: 9,
            cover_url: null,
            published_year: 1924,
          },
        ],
        catalog: [
          {
            id: 42,
            title: "Будденброки",
            cover_url: null,
            series_index: null,
            published_year: 1901,
          },
          // строка автора приходит из сущности, а не из запроса
          { id: 77, title: body.title, author: "Томас Манн", cover_url: null },
        ],
      },
      { status: 201 },
    );
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
          // задача 70: полочные совпадения рисуются карточками —
          // сервер отдаёт и статус с оценкой
          status: "read",
          rating: 9,
          title: "Волшебная гора",
          author: "Томас Манн",
          cover_url: null,
          external_id: null,
          book_id: 1,
          source: "library",
          on_shelf: true,
        },
      ];
    } else if (q.includes("тайное")) {
      // задача 90: книга в каталоге, но НЕ на полке (добавлена в цикл)
      results = [
        {
          title: "Тайное место",
          author: "Тана Френч",
          cover_url: null,
          external_id: null,
          book_id: 42,
          source: "library",
          on_shelf: false,
        },
      ];
    }
    return HttpResponse.json({ results });
  }),

  http.post("/api/v1/import", () =>
    HttpResponse.json({ imported: 2, duplicates: 1, skipped: 0 }),
  ),

  // Жанры (задача 112): справочник по каталогу + правка набора у книги
  http.get("/api/v1/genres", () =>
    HttpResponse.json({
      genres: [
        { id: 1, name: "Детектив", books: 3 },
        { id: 2, name: "Магический реализм", books: 1 },
      ],
    }),
  ),
  http.get("/api/v1/genres/:id", ({ params }) =>
    HttpResponse.json({
      id: Number(params.id),
      name: "Детектив",
      shelf: [
        { id: 1, title: "Волшебная гора", status: "read", rating: 9, cover_url: null },
      ],
      catalog: [
        { id: 42, title: "Будденброки", author: "Томас Манн", cover_url: null },
      ],
    }),
  ),
  http.put("/api/v1/books/:id/genres", async ({ params, request }) => {
    const body = await request.json();
    const genres = body.genres.map((name, i) => ({ id: 100 + i, name }));
    const book = findBook(params);
    if (book) book.genres = genres;
    return HttpResponse.json({ book_id: Number(params.id), genres });
  }),

  // Список авторов (задача 111): считаются только книги с полки
  http.get("/api/v1/authors", () =>
    HttpResponse.json({
      authors: [
        { id: 7, name: "Анна Аннова", books: 1 },
        { id: 3, name: "Томас Манн", books: 2 },
      ],
    }),
  ),

  // Рекомендации (этап 8): пусто до генерации, POST наполняет набор
  http.get("/api/v1/recommendations", () =>
    HttpResponse.json({
      recommendations: db.recommendations,
      settings: db.recSettings,   // задача 124
      genres: [
        { slug: "детектив", name: "Детектив" },
        { slug: "магический реализм", name: "Магический реализм" },
      ],
    }),
  ),
  http.put("/api/v1/recommendations/settings", async ({ request }) => {
    // бэкенд отбрасывает жанры, которых нет в справочнике; мок принимает как есть
    db.recSettings = await request.json();
    return HttpResponse.json({ settings: db.recSettings });
  }),
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
      undated_read: 2,   // задача 98: прочитаны, но дата неизвестна
    }),
  ),
  // Задача 84: расход на AI и acceptance rate (эндпоинт только для админа)
  http.get("/api/v1/stats/ai", () =>
    HttpResponse.json({
      period_days: null,
      usage: {
        calls: 3,
        input_tokens: 310,
        output_tokens: 135,
        providers: [
          {
            provider: "Claude", calls: 2, errors: 0,
            input_tokens: 110, output_tokens: 55, avg_latency_ms: 1500,
          },
          {
            provider: "ChatGPT", calls: 1, errors: 1,
            input_tokens: 200, output_tokens: 80, avg_latency_ms: 3000,
          },
        ],
      },
      feedback: {
        total: 4,
        sources: [
          { source: "Claude", up: 2, down: 1, total: 3, acceptance: 0.67 },
          { source: "ChatGPT", up: 0, down: 1, total: 1, acceptance: 0.0 },
        ],
      },
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

  // Циклы книг (задача 89): в тестах пустая полка
  http.get("/api/v1/series", () => HttpResponse.json({ series: [] })),

  // Страница цикла (задача 89): в списке есть и книга с полки, и том, которого
  // на полке нет, — второй с 03.08 тоже кликабельный.
  // ⚠ Форма ответа взята из `services/series.series_card`: там есть `progress`
  // с полями total/read/on_shelf/next_book, и без него шапка цикла падает.
  http.get("/api/v1/series/:id", ({ params }) => {
    const books = [
      {
        id: 1,
        title: "В лесной чаще",
        author: "Тана Френч",
        cover_url: null,
        series_index: 1,
        status: "read",
        rating: 8,
        on_shelf: true,
      },
      {
        id: 77,
        title: "Тень за спиной",
        author: "Тана Френч",
        cover_url: null,
        series_index: 6,
        status: null,
        rating: null,
        on_shelf: false,
      },
    ];
    return HttpResponse.json({
      id: Number(params.id),
      name: "Дублинский отдел убийств",
      author: "Тана Френч",
      description: null,
      design: null,
      status: "reading",
      progress: {
        total: books.length,
        read: 1,
        on_shelf: 1,
        next_book: books[1],
      },
      books,
    });
  }),

  // Обратная связь по подборкам (задача 26): stateful — воспроизводим toggle
  // бэкенда (повтор того же вердикта снимает оценку)
  http.get("/api/v1/feedback", () =>
    HttpResponse.json({ feedback: { ...db.feedback } }),
  ),
  http.post("/api/v1/feedback", async ({ request }) => {
    const { ref, verdict } = await request.json();
    if (db.feedback[ref] === verdict) {
      delete db.feedback[ref]; // тот же вердикт повторно → снять
      return HttpResponse.json({ ref, verdict: null });
    }
    db.feedback[ref] = verdict;
    return HttpResponse.json({ ref, verdict });
  }),

  // Точечное удаление трека (admin): бэкенд отдаёт подборку уже без него
  http.delete(
    "/api/v1/books/:id/atmosphere/music/tracks",
    async ({ params, request }) => {
      const { source } = await request.json();
      return HttpResponse.json({
        book_id: Number(params.id),
        category: "music",
        verified: true,
        selections: ["Claude", "ChatGPT"].map((s) => ({
          source: s,
          payload: s === source ? [] : [{ title: "Song A", artist: "Artist A" }],
          explanation: `${s} explanation`,
        })),
      });
    },
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
      verified: true, // задача 85: в тестах Spotify «доступен»
      selections: ["Claude", "ChatGPT"].map((source) => ({
        source,
        payload: fixtures[params.category] ?? [],
        explanation: `${source} explanation`,
      })),
    });
  }),
];

export const server = setupServer(...handlers);
