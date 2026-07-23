// Фикстуры и перехват API для визуальной регрессии (задача 86).
//
// Скриншот-тест бесполезен, если картинка каждый раз разная. Поэтому:
//  - API отдаёт ФИКСИРОВАННЫЕ данные (не живой бэкенд);
//  - AI-паспорт задан жёстко (палитра книги иначе случайна);
//  - внешние шрифты и обложки блокируются (грузятся асинхронно → мельтешат);
//  - анимации/переходы отключены (инъекция CSS).
// Тогда единственная причина «диффа» — реальное изменение вёрстки.

const BOOKS = [
  {
    id: 1, user_id: 1, title: "Волшебная гора", author: "Томас Манн",
    cover_url: null, description: "Роман о санатории в Альпах.",
    status: "read", rating: 9, created_at: "2026-07-01T10:00:00",
    page_count: 900, categories: '["Fiction"]', published_year: 1924,
    language: "ru", external_rating: 4.2, isbn: null, enrich_status: "ready",
    spotify_playlist_url: null, updated_at: null, read_at: "2026-07-05T00:00:00",
    series_id: null, series_index: null, series_name: null,
  },
  {
    id: 2, user_id: 1, title: "Имя розы", author: "Умберто Эко",
    cover_url: null, description: "Детектив в средневековом монастыре.",
    status: "reading", rating: null, created_at: "2026-07-03T10:00:00",
    page_count: 600, categories: '["Fiction"]', published_year: 1980,
    language: "ru", external_rating: 4.1, isbn: null, enrich_status: "ready",
    spotify_playlist_url: null, updated_at: null, read_at: null,
    series_id: null, series_index: null, series_name: null,
  },
  {
    id: 3, user_id: 1, title: "Дюна", author: "Фрэнк Герберт",
    cover_url: null, description: "Пустынная планета Арракис.",
    status: "want", rating: null, created_at: "2026-07-04T10:00:00",
    page_count: 700, categories: '["Sci-Fi"]', published_year: 1965,
    language: "ru", external_rating: 4.5, isbn: null, enrich_status: "ready",
    spotify_playlist_url: null, updated_at: null, read_at: null,
    series_id: null, series_index: null, series_name: null,
  },
];

const DESIGN = {
  book_id: 1, category: "design",
  selections: [{
    source: "Claude",
    payload: {
      base_mood: "альпийская тишина",
      palette_dark: {
        bg: "#161311", surface: "#221c17", accent: "#e08b2d",
        text: "#e9e1d3", muted: "#a19585",
      },
      palette_light: {
        bg: "#f6f1e7", surface: "#fffaf0", accent: "#b05e12",
        text: "#2a241d", muted: "#6d655b",
      },
      title_font: "Georgia", body_font: "Georgia",
      statement: "Снежная гора — символ отрешённости от времени.",
      symbol_svg: '<svg viewBox="0 0 100 100"><path d="M20 75 L50 25 L80 75 Z" fill="#e08b2d"/></svg>',
    },
    explanation: "Снежная гора — символ отрешённости от времени.",
  }],
};

const ATMOSPHERE = {
  music: [{ title: "Spiegel im Spiegel", artist: "Arvo Pärt" }],
  food: [{ title: "Горячий шоколад", description: "Густой, по-альпийски." }],
  aroma: [{ title: "Кедр", description: "Хвойный, холодный." }],
};

// Точное совпадение пути → JSON-ответ. Порядок проверки — от специфичных к общим.
const ROUTES = [
  [/\/api\/v1\/books\/design-summary$/, { designs: [] }],
  [/\/api\/v1\/books\/pending-count$/, { pending: 0 }],
  [/\/api\/v1\/books\/1$/, BOOKS[0]],
  [/\/api\/v1\/books\/1\/atmosphere\/design$/, DESIGN],
  [/\/api\/v1\/books\/1\/atmosphere\/music$/, {
    book_id: 1, category: "music", verified: true,
    selections: [{ source: "Claude", payload: ATMOSPHERE.music, explanation: "Тихо и медленно." }],
  }],
  [/\/api\/v1\/books\/1\/atmosphere\/food$/, {
    book_id: 1, category: "food",
    selections: [{ source: "Claude", payload: ATMOSPHERE.food, explanation: "Тепло." }],
  }],
  [/\/api\/v1\/books\/1\/atmosphere\/aroma$/, {
    book_id: 1, category: "aroma",
    selections: [{ source: "Claude", payload: ATMOSPHERE.aroma, explanation: "Хвоя." }],
  }],
  [/\/api\/v1\/books(\?|$)/, BOOKS],
  [/\/api\/v1\/series$/, { series: [] }],
  [/\/api\/v1\/recommendations$/, { recommendations: [] }],
  [/\/api\/v1\/feedback$/, { feedback: {} }],
];

export async function setupVisualMocks(page) {
  // блокируем внешние ресурсы (шрифты, картинки) — источник мельтешения
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());

  await page.route(/\/api\/v1\//, (route) => {
    const url = route.request().url();
    for (const [pattern, body] of ROUTES) {
      if (pattern.test(url)) {
        return route.fulfill({ json: body });
      }
    }
    return route.fulfill({ json: {} }); // прочее — пустой ответ, не 404
  });

  // отключаем анимации и переходы — детерминированный кадр
  await page.addStyleTag({
    content: `*, *::before, *::after {
      animation: none !important;
      transition: none !important;
    }`,
  });
}
