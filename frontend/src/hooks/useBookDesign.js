// Паспорт оформления книги: запрос, палитра под тему, символ-экслибрис,
// CSS-переменные карточки, подключение шрифтов и «ленивая» автогенерация.
//
// Вынесено из BookDetail (ревью 19.07): компонент держал всё это в себе и
// разросся до 380 строк. Здесь — только логика паспорта, без вёрстки.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { bestTextOn, hasReadableContrast, withAlpha } from "../lib/contrast";
import { pickPalette } from "../lib/palette";
import { centeredSvgDataUri } from "../lib/svg";

export function useBookDesign(bookId, theme) {
  const queryClient = useQueryClient();

  // Паспорт — единый формат атмосферы: payload единственного источника.
  // Ошибку не обрабатываем: не загрузился — карточка в базовой теме.
  const { data } = useQuery({
    queryKey: keys.atmosphere(bookId, "design"),
    queryFn: () => api.getAtmosphere(bookId, "design"),
  });
  const design = data?.selections?.[0]?.payload ?? null;

  // Символ: перецентровка viewBox по реальным границам рисунка (мемо —
  // внутри работа с DOM, незачем повторять на каждый рендер)
  const symbolUri = useMemo(
    () => (design?.symbol_svg ? centeredSvgDataUri(design.symbol_svg) : null),
    [design?.symbol_svg],
  );
  // символ мог сгенерироваться битым (обрезанный/невалидный SVG) — <img> не
  // отрисуется, ловим onError и прячем символ
  const [symbolBroken, setSymbolBroken] = useState(false);
  const symbolOk = Boolean(symbolUri) && !symbolBroken;

  const palette = pickPalette(design, theme);
  // Задача 23: применяем AI-палитру, только если текст читаем на её фоне (WCAG AA)
  const appliedDesign =
    design && palette && hasReadableContrast(palette.text, palette.bg)
      ? design
      : null;

  const generation = useMutation({
    mutationFn: () => api.generateAtmosphere(bookId, "design"),
    // POST и GET атмосферы отдают один формат — кладём ответ прямо в кэш
    onSuccess: (fresh) =>
      queryClient.setQueryData(keys.atmosphere(bookId, "design"), fresh),
  });

  // Задача 57: оформление без кнопки. Паспорта нет (книга из CSV/старая, или
  // фон при добавлении не успел/упал) либо он старого формата без светлой
  // палитры — тихо генерируем один раз при открытии.
  const autoFired = useRef(false);
  const generate = generation.mutate;
  useEffect(() => {
    if (!data || autoFired.current) return;
    if (!design || !design.palette_light) {
      autoFired.current = true;
      generate();
    }
  }, [data, design, generate]);

  // Шрифты паспорта (Google Fonts) — только если палитра реально применяется
  useEffect(() => {
    if (!appliedDesign) return;
    const families = [appliedDesign.title_font, appliedDesign.body_font]
      .map((f) => f.trim().replace(/ /g, "+"))
      .join("&family=");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${families}&display=swap`;
    document.head.appendChild(link);
    return () => document.head.removeChild(link);
  }, [appliedDesign]);

  // Паспорт → CSS-переменные (наследуются всеми детьми карточки).
  // Статические отступы — в классе .detail-themed (styles/detail.css)
  const themedStyle = appliedDesign
    ? {
        "--surface": palette.surface,
        "--accent": palette.accent,
        // задача 49: текст на accent — по контрасту (тема сюда не дотягивается)
        "--on-accent": bestTextOn(palette.accent),
        "--text": palette.text,
        "--muted": palette.muted,
        // задача 49: границы — полупрозрачный muted, чтобы не сливались с текстом
        "--border": withAlpha(palette.muted, "66"),
        "--serif": `'${appliedDesign.title_font}', Georgia, serif`,
        background: palette.bg,
        color: palette.text,
        fontFamily: `'${appliedDesign.body_font}', system-ui, sans-serif`,
      }
    : {};

  return {
    design,
    appliedDesign,
    themedStyle,
    symbolUri,
    symbolOk,
    onSymbolError: () => setSymbolBroken(true),
    generating: generation.isPending,
    generationError: generation.isError ? generation.error : null,
  };
}
