// Проверка контраста по WCAG (задача 23).
// Используется для AI-палитры паспорта оформления: если сгенерированные
// цвета текста и фона не дают читаемого контраста, карточка остаётся
// в базовой теме (мягкий fallback вместо нечитаемого оформления).

function parseHex(color) {
  if (typeof color !== "string") return null;
  const m = color.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!m) return null;
  let hex = m[1];
  if (hex.length === 3)
    hex = hex
      .split("")
      .map((c) => c + c)
      .join("");
  const int = parseInt(hex, 16);
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255];
}

function luminance([r, g, b]) {
  const chan = (v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
}

export function contrastRatio(fg, bg) {
  const a = parseHex(fg);
  const b = parseHex(bg);
  if (!a || !b) return null; // не hex-цвет — посчитать не можем
  const l1 = luminance(a);
  const l2 = luminance(b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

// AA для обычного текста — 4.5:1. Нераспознанные цвета считаем нечитаемыми:
// лучше показать базовую тему, чем рискнуть нечитаемой карточкой.
export function hasReadableContrast(fg, bg, threshold = 4.5) {
  const ratio = contrastRatio(fg, bg);
  return ratio !== null && ratio >= threshold;
}

// Задача 49: контрастный цвет текста для произвольного фона (accent паспорта)
export function bestTextOn(bg, light = "#ffffff", dark = "#1c1610") {
  const lightRatio = contrastRatio(light, bg) ?? 0;
  const darkRatio = contrastRatio(dark, bg) ?? 0;
  return lightRatio >= darkRatio ? light : dark;
}

// --- Дотягивание цвета до читаемого контраста (аудит 28.07, находка 7) ---
//
// Проверка hasReadableContrast закрывала только пару текст/фон, а accent
// паспорта не проверялся вовсе — при этом он идёт и в текст (statement), и в
// фон под белыми буквами. У книги 187 модель выдала #b5652f: как текст на своём
// фоне это 3.6:1 при норме 4.5. Отвергать всю палитру из-за одного цвета жалко,
// поэтому цвет не бракуется, а затемняется (или осветляется — смотря что за фон)
// шагами по светлоте, пока не наберёт норму. Характер цвета сохраняется:
// тон и насыщенность не трогаем.

function toHsl([r, g, b]) {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
  }
  return [h, s, l];
}

function hslToHex(h, s, l) {
  const hue = (p, q, t) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  let r;
  let g;
  let b;
  if (s === 0) {
    r = g = b = l;
  } else {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue(p, q, h + 1 / 3);
    g = hue(p, q, h);
    b = hue(p, q, h - 1 / 3);
  }
  const hex = (v) =>
    Math.round(v * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

export function ensureContrast(color, bg, threshold = 4.5) {
  const start = contrastRatio(color, bg);
  if (start === null) return color; // не hex — считать нечем, оставляем как есть
  if (start >= threshold) return color;

  const rgb = parseHex(color);
  const bgRgb = parseHex(bg);
  const [h, s, l] = toHsl(rgb);
  // на светлом фоне цвет темнеет, на тёмном — светлеет
  const direction = luminance(bgRgb) > 0.5 ? -1 : 1;

  // шаг 0.025 по светлоте, до 40 шагов — это вся шкала от исходного цвета до
  // чёрного или белого: насыщенным цветам (жёлтый, салатовый) до нормы далеко
  let best = color;
  for (let step = 1; step <= 40; step++) {
    const next = Math.min(1, Math.max(0, l + direction * step * 0.025));
    const candidate = hslToHex(h, s, next);
    best = candidate;
    if (contrastRatio(candidate, bg) >= threshold) return candidate;
    if (next === 0 || next === 1) break; // упёрлись в чёрный/белый
  }
  return best; // норму не набрали — отдаём максимально контрастный из найденных
}

// --- Акцент паспорта в двух ролях сразу (аудит 01.08) ---
//
// Акцент из паспорта книги работает и как ТЕКСТ на фоне сцены (statement),
// и как ФОН под белыми буквами (кнопки, пилюли). Проверять надо обе роли:
// аудит показал 3.84:1 у statement и 4.41:1 у текста на кнопке — то есть
// дотянуть только первую было недостаточно.
//
// ⚠ Настоящая причина бага была не в арифметике, а в дублировании: страница
// книги дотягивала акцент, «вечер» — нет, потому что логика жила в двух местах
// и правку 28.07 перенесли только в одно. Теперь она здесь одна, и обе
// страницы зовут её.
//
// Порядок шагов важен: сначала акцент как текст на фоне, потом выбор цвета
// букв, потом акцент как фон под этими буквами. В практических случаях оба
// шага двигают цвет в одну сторону: bestTextOn выбирает тёмные буквы только
// для светлого акцента, а он к этому моменту уже затемнён первым шагом.
export function accentPair(accent, bg) {
  const asText = ensureContrast(accent, bg);
  const onAccent = bestTextOn(asText);
  return { accent: ensureContrast(asText, onAccent), onAccent };
}

// Задача 49: hex-цвет с прозрачностью (для границ из muted паспорта)
export function withAlpha(hex, alpha = "66") {
  const m = hex?.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!m) return hex;
  let h = m[1];
  if (h.length === 3)
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  return `#${h}${alpha}`;
}
