// Аудит вёрстки (28.07): скриншоты + машинные замеры на трёх ширинах.
//
// Зачем скрипт, а не «посмотреть глазами»: находки становятся воспроизводимыми —
// после правок прогоняем ещё раз и сравниваем report.json. Эмулятор не заменяет
// живой телефон (грабли 24.07), но ловит измеримое: переполнение по ширине,
// тач-таргеты <44px, шрифт полей <16px, обрезанный текст.
//
// Запуск (из frontend/, при поднятых dev-сервере и бэкенде):
//   node scripts/layout-audit.mjs
// Бэкенд нужен с ALLOW_DEV_LOGIN=1 — иначе закрытые страницы упрутся во вход:
//   cd backend; $env:ALLOW_DEV_LOGIN="1"; uvicorn main:app --reload
//
// Результат — в docs/audit-28.07/: PNG по странице на каждую ширину + report.json.
import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "../../docs/audit-28.07");
const BASE = process.env.AUDIT_BASE || "http://localhost:5173";
const DIRECT_API = process.env.AUDIT_API || "http://127.0.0.1:8000";
const SLUG = process.env.AUDIT_SLUG || "publiclib";

const VIEWPORTS = [
  { name: "390", width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  { name: "768", width: 768, height: 1024, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  { name: "1440", width: 1440, height: 900, isMobile: false, hasTouch: false, deviceScaleFactor: 1 },
];

// ---------------------------------------------------------------- замеры в браузере
// Выполняется в контексте страницы. Возвращает только «измеримое»: то, что можно
// перепроверить числом, а не мнением.
function measure() {
  const vw = window.innerWidth;
  const pageW = document.documentElement.clientWidth;
  const MIN_TAP = 44;

  const shortSel = (el) => {
    const parts = [];
    let node = el;
    for (let i = 0; node && i < 3; i++) {
      let p = node.tagName.toLowerCase();
      if (node.id) p += "#" + node.id;
      else if (node.className && typeof node.className === "string") {
        const cls = node.className.trim().split(/\s+/).slice(0, 2).join(".");
        if (cls) p += "." + cls;
      }
      parts.unshift(p);
      node = node.parentElement;
      if (node === document.body) break;
    }
    return parts.join(" > ");
  };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && s.opacity !== "0";
  };

  const all = [...document.querySelectorAll("body *")].filter(visible);
  const txt = (el) => (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 48);

  // Элемент внутри горизонтальной прокрутки (полка-свайп) — не переполнение,
  // а задуманное поведение. Такие пропускаем.
  const inScroller = (el) => {
    let n = el.parentElement;
    while (n && n !== document.body) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === "auto" || ox === "scroll") return true;
      n = n.parentElement;
    }
    return false;
  };

  // 1. Горизонтальное переполнение СТРАНИЦЫ. Оставляем только «внешних»
  //    виновников: если родитель уже вылезает, дети не новость.
  const overflowing = all.filter((el) => {
    if (inScroller(el)) return false;
    const r = el.getBoundingClientRect();
    return r.right > pageW + 1 || r.left < -1;
  });
  const outermost = overflowing.filter((el) => !overflowing.includes(el.parentElement));
  const overflow = outermost.slice(0, 15).map((el) => {
    const r = el.getBoundingClientRect();
    return {
      sel: shortSel(el),
      left: Math.round(r.left),
      right: Math.round(r.right),
      width: Math.round(r.width),
      overBy: Math.round(r.right - pageW),
      text: txt(el),
    };
  });

  // 1b. Переполнение СВОЕГО контейнера: текст вылезает за паддинг карточки,
  //     хотя до края экрана не достаёт. Так ловится длинный заголовок.
  const boxOverflow = [];
  for (const el of all) {
    if (inScroller(el) || el.children.length > 0) continue;
    const parent = el.parentElement;
    if (!parent) continue;
    const pr = parent.getBoundingClientRect();
    const ps = getComputedStyle(parent);
    if (ps.overflow !== "visible") continue;
    const innerRight = pr.right - parseFloat(ps.paddingRight || 0);
    const r = el.getBoundingClientRect();
    if (r.right > innerRight + 2) {
      boxOverflow.push({
        sel: shortSel(el),
        overBy: Math.round(r.right - innerRight),
        text: txt(el),
      });
    }
  }

  // 2. Тач-таргеты меньше 44×44 (правило Apple HIG / WCAG 2.5.5)
  const controls = all.filter((el) =>
    el.matches('a, button, input:not([type="file"]), select, textarea, summary, [role="button"]'),
  );
  const smallTaps = controls
    .map((el) => {
      const r = el.getBoundingClientRect();
      return { sel: shortSel(el), w: Math.round(r.width), h: Math.round(r.height), text: txt(el) };
    })
    .filter((x) => x.w < MIN_TAP || x.h < MIN_TAP);

  // 3. Поля с шрифтом <16px — iOS Safari зумит страницу при фокусе и не отъезжает
  const smallInputs = all
    .filter((el) => el.matches("input, select, textarea"))
    .map((el) => ({ sel: shortSel(el), fontSize: parseFloat(getComputedStyle(el).fontSize) }))
    .filter((x) => x.fontSize < 16);

  // 4. Обрезанный текст: содержимое шире контейнера (ellipsis или просто срез)
  const clipped = all
    .filter((el) => el.children.length === 0 && el.scrollWidth > el.clientWidth + 1 && txt(el))
    .slice(0, 15)
    .map((el) => ({
      sel: shortSel(el),
      scrollW: el.scrollWidth,
      clientW: el.clientWidth,
      text: txt(el),
    }));

  // 5. Мелкий текст (<12px) — на телефоне читается плохо
  const tiny = [
    ...new Set(
      all
        .filter((el) => el.children.length === 0 && txt(el))
        .filter((el) => parseFloat(getComputedStyle(el).fontSize) < 12)
        .map((el) => shortSel(el) + " @" + getComputedStyle(el).fontSize),
    ),
  ].slice(0, 10);

  // 6. Контраст текста (WCAG 1.4.3). Считаем по фактически вычисленным цветам:
  //    так ловится случай «страница в палитре книги, а кнопка из темы».
  const parseRGB = (s) => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(",").map((x) => parseFloat(x));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const bgOf = (el) => {
    let n = el;
    while (n) {
      const c = parseRGB(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.9) return c;
      n = n.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  };
  const lum = (c) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const contrast = (a, b) => {
    const l1 = lum(a);
    const l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };

  const lowContrast = [];
  const seenContrast = new Set();
  for (const el of all) {
    if (el.children.length > 0 || !txt(el)) continue;
    const cs = getComputedStyle(el);
    const fg = parseRGB(cs.color);
    if (!fg || fg.a < 0.1) continue;
    const size = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    const ratio = contrast(fg, bgOf(el));
    if (ratio < need) {
      const key = shortSel(el) + Math.round(ratio * 10);
      if (seenContrast.has(key)) continue;
      seenContrast.add(key);
      lowContrast.push({
        sel: shortSel(el),
        ratio: Math.round(ratio * 100) / 100,
        need,
        fontSize: size,
        color: cs.color,
        text: txt(el),
      });
    }
  }

  return {
    vw,
    pageW,
    // насколько эмуляция вообще похожа на телефон: от этого зависит,
    // применились ли правила @media (pointer: coarse) с тач-таргетами 44px
    pointerCoarse: matchMedia("(pointer: coarse)").matches,
    hoverHover: matchMedia("(hover: hover)").matches,
    docScrollWidth: document.documentElement.scrollWidth,
    docScrollHeight: document.documentElement.scrollHeight,
    hasHorizontalScroll: document.documentElement.scrollWidth > pageW + 1,
    overflow,
    boxOverflow: boxOverflow.slice(0, 15),
    smallTaps,
    smallInputs,
    clipped,
    tiny,
    lowContrast: lowContrast.slice(0, 20),
  };
}

// Сколько строк занимает флекс-контейнер (перенос кнопок в шапке).
function measureRows(selector) {
  const box = document.querySelector(selector);
  if (!box) return null;
  const kids = [...box.children].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  // строки считаем с допуском: соседние кнопки разной высоты стоят на одной
  // строке, но их top отличается на несколько пикселей из-за выравнивания
  const tops = [];
  for (const el of kids) {
    const t = el.getBoundingClientRect().top;
    if (!tops.some((x) => Math.abs(x - t) < 12)) tops.push(t);
  }
  return {
    selector,
    children: kids.length,
    rows: tops.length,
    rowTops: tops.map((t) => Math.round(t)),
    height: Math.round(box.getBoundingClientRect().height),
  };
}

// ---------------------------------------------------------------- запуск
async function pickTargets(request) {
  const shelf = await (await request.get("/api/v1/books?status=read&limit=100")).json();
  const books = shelf.items || shelf;
  const byLen = [...books].sort(
    (a, b) => (b.title + b.author).length - (a.title + a.author).length,
  );
  const noCover = books.find((b) => !b.cover_url);
  const withPlaylist = books.find((b) => b.spotify_playlist_url);
  const shortest = [...byLen].reverse()[0];

  // 3–4 книги в витрину: длинное название, книга без обложки, книга с плейлистом,
  // короткое название — так видно и переполнение, и фолбэки.
  const featured = [...new Set([byLen[0], noCover, withPlaylist, shortest].filter(Boolean))].slice(0, 4);
  for (const b of featured) {
    await request.patch(`/api/v1/books/${b.id}`, { data: { featured: true } });
  }

  let seriesId = null;
  const seriesResp = await request.get("/api/v1/series");
  if (seriesResp.ok()) {
    const arr = (await seriesResp.json()).series || [];
    if (arr.length) seriesId = arr[0].id;
  }

  return {
    featured: featured.map((b) => ({ id: b.id, title: b.title })),
    showcaseBookId: (withPlaylist || byLen[0]).id,
    bookId: (withPlaylist || byLen[0]).id,
    seriesId,
  };
}

async function run() {
  await fs.mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();
  const report = { base: BASE, generatedAt: new Date().toISOString(), pages: [] };

  // вход служебным эндпоинтом — тот же приём, что в e2e
  const auth = await browser.newContext({ baseURL: BASE });
  let login = await auth.request.post("/api/v1/auth/dev-login");

  // Запасной путь: логинимся напрямую в бэкенд и переносим куку на localhost.
  // Нужен, когда dev-сервер не проксирует /api или на :8000 отвечает не тот
  // процесс — сессия всё равно подходит: секрет и база у них общие.
  if (!login.ok() && DIRECT_API) {
    const direct = await auth.request
      .post(`${DIRECT_API}/api/v1/auth/dev-login`)
      .catch(() => null);
    if (direct?.ok()) {
      const jar = await auth.cookies();
      const session = jar.find((c) => c.name === "nocturne_session");
      if (session) {
        await auth.addCookies([
          { name: session.name, value: session.value, domain: "localhost", path: "/" },
        ]);
        console.log(`Вход выполнен напрямую через ${DIRECT_API} (прокси не сработал).`);
        login = direct;
      }
    }
  }

  if (!login.ok()) {
    // Диагностика: отличить «эндпоинта нет» (бэкенд без ALLOW_DEV_LOGIN)
    // от «запрос не доехал» (dev-сервер не проксирует /api).
    const probe = async (url) => {
      try {
        const r = await auth.request.post(url);
        return `${r.status()} ${(await r.text()).slice(0, 120).replace(/\s+/g, " ")}`;
      } catch (e) {
        return "нет связи: " + String(e).slice(0, 120);
      }
    };
    const viaProxy = `${login.status()} ${(await login.text()).slice(0, 120).replace(/\s+/g, " ")}`;
    const direct = await probe(`${DIRECT_API}/api/v1/auth/dev-login`);
    await browser.close();
    throw new Error(
      "Служебный вход недоступен.\n" +
        `  через ${BASE} (прокси Vite): ${viaProxy}\n` +
        `  напрямую ${DIRECT_API}:        ${direct}\n\n` +
        "405 Method Not Allowed = маршрута нет, POST упал в catch-all раздачи dist/.\n" +
        "Значит отвечающий процесс поднят БЕЗ ALLOW_DEV_LOGIN=1 — скорее всего на\n" +
        "порту висит второй, старый uvicorn. Кто слушает :8000:\n" +
        "  Get-NetTCPConnection -LocalPort 8000 -State Listen | Select LocalAddress, OwningProcess\n\n" +
        "Обходной путь без разбирательств — поднять свежий бэкенд на другом порту:\n" +
        '  cd backend; $env:ALLOW_DEV_LOGIN="1"; uvicorn main:app --port 8001\n' +
        '  cd frontend; $env:AUDIT_API="http://127.0.0.1:8001"; node scripts/layout-audit.mjs',
    );
  }
  const targets = await pickTargets(auth.request);
  const storage = await auth.storageState();
  await auth.close();
  report.targets = targets;

  const PAGES = [
    // приоритет 1 — витрина: её никто не видел на реальных экранах
    { name: "showcase", url: `/u/${SLUG}`, theme: "light" },
    { name: "showcase-dark", url: `/u/${SLUG}`, theme: "dark" },
    { name: "showcase-book", url: `/u/${SLUG}/books/${targets.showcaseBookId}`, theme: "light" },
    { name: "showcase-book-dark", url: `/u/${SLUG}/books/${targets.showcaseBookId}`, theme: "dark" },
    // приоритет 2 — шапка главной после этапа 9
    { name: "home", url: "/", theme: "light", fullPage: false, rowsOf: ".header-actions" },
    { name: "home-dark", url: "/", theme: "dark", fullPage: false, rowsOf: ".header-actions" },
    // приоритет 3 — страница книги (строка трека .song) и цикл
    { name: "book", url: `/books/${targets.bookId}`, theme: "light" },
    ...(targets.seriesId
      ? [{ name: "series", url: `/series/${targets.seriesId}`, theme: "light" }]
      : []),
    { name: "stats", url: "/stats", theme: "light" },
    { name: "evening", url: `/books/${targets.bookId}/evening`, theme: "light", fullPage: false },
    { name: "card", url: `/books/${targets.bookId}/card`, theme: "light" },
  ];

  for (const vp of VIEWPORTS) {
    for (const p of PAGES) {
      const context = await browser.newContext({
        baseURL: BASE,
        storageState: storage,
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: vp.deviceScaleFactor,
        isMobile: vp.isMobile,
        hasTouch: vp.hasTouch,
      });
      // тему кладём ДО загрузки — useTheme читает localStorage при первом рендере
      await context.addInitScript((theme) => {
        try {
          localStorage.setItem("theme", theme);
        } catch { /* приватный режим */ }
      }, p.theme);

      const page = await context.newPage();
      // Playwright задаёт тач-события, но НЕ медиа-признаки: без этого правила
      // @media (pointer: coarse) с тач-таргетами 44px не применяются и замер
      // врёт. Включаем их через CDP — иначе эмуляция «телефона» не телефон.
      if (vp.isMobile) {
        const cdp = await context.newCDPSession(page);
        await cdp
          .send("Emulation.setEmulatedMedia", {
            features: [
              { name: "pointer", value: "coarse" },
              { name: "any-pointer", value: "coarse" },
              { name: "hover", value: "none" },
              { name: "any-hover", value: "none" },
            ],
          })
          .catch(() => {});
      }
      const consoleErrors = [];
      page.on("console", (m) => {
        if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200));
      });
      page.on("pageerror", (e) => consoleErrors.push("pageerror: " + String(e).slice(0, 200)));

      const entry = { page: p.name, viewport: vp.name, url: p.url };
      try {
        await page.goto(p.url, { waitUntil: "domcontentloaded", timeout: 20000 });
        await page.waitForSelector("h1, .error, .muted", { timeout: 15000 }).catch(() => {});
        await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
        // дожидаемся картинок — иначе обложки попадут в кадр пустыми
        await page
          .evaluate(
            () =>
              Promise.race([
                Promise.all(
                  [...document.images]
                    .filter((i) => !i.complete)
                    .map((i) => new Promise((r) => { i.onload = i.onerror = r; })),
                ),
                new Promise((r) => setTimeout(r, 4000)),
              ]),
          )
          .catch(() => {});

        const shot = path.join(OUT, `${p.name}-${vp.name}.png`);
        await page.screenshot({ path: shot, fullPage: p.fullPage !== false });
        entry.screenshot = path.basename(shot);
        entry.metrics = await page.evaluate(measure);
        if (p.rowsOf) entry.rows = await page.evaluate(measureRows, p.rowsOf);
        entry.consoleErrors = consoleErrors.slice(0, 5);
      } catch (e) {
        entry.error = String(e).slice(0, 300);
      }
      report.pages.push(entry);
      console.log(
        `${p.name} @${vp.name}: ` +
          (entry.error
            ? "ОШИБКА " + entry.error
            : `overflow=${entry.metrics.overflow.length} вне-контейнера=${entry.metrics.boxOverflow.length} ` +
              `taps<44=${entry.metrics.smallTaps.length} контраст=${entry.metrics.lowContrast.length} ` +
              `coarse=${entry.metrics.pointerCoarse}`),
      );
      await context.close();
    }
  }

  await browser.close();
  await fs.writeFile(path.join(OUT, "report.json"), JSON.stringify(report, null, 2), "utf8");
  console.log(`\nГотово. Скриншоты и report.json — в ${OUT}`);
  console.log(
    "В витрину отмечены книги: " +
      targets.featured.map((b) => `${b.id} «${b.title}»`).join(", ") +
      "\n(снять отметку — кнопкой «В витрине» на странице книги)",
  );
}

run().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
