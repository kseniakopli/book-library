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
