// Карточка книги: паспорт оформления, статус/оценка, действия.
// Секция «Атмосфера» вынесена в AtmosphereSection (R7).
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { STATUS_LABELS, STATUSES } from "../constants";
import { hasReadableContrast } from "../lib/contrast";
import AtmosphereSection from "./AtmosphereSection";

function BookDetail({ book, onBack, onDeleted }) {
  const queryClient = useQueryClient();

  // Паспорт оформления: единый формат атмосферы, паспорт — payload единственного источника.
  // Без обработки ошибки: не загрузился — карточка в базовой теме.
  const { data: designData } = useQuery({
    queryKey: keys.atmosphere(book.id, "design"),
    queryFn: () => api.getAtmosphere(book.id, "design"),
  });
  const design = designData?.selections?.[0]?.payload ?? null;

  // Задача 23: применяем AI-палитру, только если текст читаем на её фоне (WCAG AA).
  const appliedDesign =
    design && hasReadableContrast(design.palette?.text, design.palette?.bg)
      ? design
      : null;

  // --- Мутации ---
  const patchMutation = useMutation({
    mutationFn: (body) => api.patchBook({ id: book.id, ...body }),
    // инвалидация по префиксу keys.books: обновятся и список, и эта карточка
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });
  const saving = patchMutation.isPending;

  const designMutation = useMutation({
    mutationFn: () => api.generateAtmosphere(book.id, "design"),
    // POST и GET атмосферы отдают один формат — кладём ответ прямо в кэш
    onSuccess: (fresh) =>
      queryClient.setQueryData(keys.atmosphere(book.id, "design"), fresh),
  });

  const enrichMutation = useMutation({
    mutationFn: () => api.enrichBook(book.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteBook(book.id),
    onSuccess: onDeleted, // BookPage: инвалидация + возврат на главную
  });

  function removeBook() {
    if (
      !window.confirm(
        `Удалить «${book.title}»? Подборки и оформление тоже удалятся.`,
      )
    )
      return;
    deleteMutation.mutate();
  }

  // Подключаем шрифты из паспорта (Google Fonts) — только если палитра применяется
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

  // Паспорт → CSS-переменные и шрифты (наследуются всеми детьми карточки).
  // Статические отступы — в классе .detail-themed (styles/detail.css)
  const themedStyle = appliedDesign
    ? {
        "--surface": appliedDesign.palette.surface,
        "--accent": appliedDesign.palette.accent,
        "--text": appliedDesign.palette.text,
        "--muted": appliedDesign.palette.muted,
        "--border": appliedDesign.palette.muted,
        "--serif": `'${appliedDesign.title_font}', Georgia, serif`,
        background: appliedDesign.palette.bg,
        color: appliedDesign.palette.text,
        fontFamily: `'${appliedDesign.body_font}', system-ui, sans-serif`,
      }
    : {};

  return (
    <div
      className={"detail" + (appliedDesign ? " detail-themed" : "")}
      style={themedStyle}
    >
      <div className="detail-bar">
        <button className="btn-ghost" onClick={onBack}>
          ← К библиотеке
        </button>
        <div className="detail-bar-actions">
          <button
            className="btn-ghost"
            onClick={() => enrichMutation.mutate()}
            disabled={enrichMutation.isPending}
          >
            {enrichMutation.isPending ? "Обновляю…" : "Обновить информацию"}
          </button>
          <button
            className="add-btn"
            onClick={() => designMutation.mutate()}
            disabled={designMutation.isPending}
          >
            {designMutation.isPending
              ? "Оформляю…"
              : design
                ? "Обновить оформление"
                : "Оформить под книгу"}
          </button>
          <button
            className="btn-ghost"
            onClick={removeBook}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Удаляю…" : "Удалить"}
          </button>
        </div>
      </div>

      {(patchMutation.isError ||
        designMutation.isError ||
        enrichMutation.isError ||
        deleteMutation.isError) && (
        <p className="error">
          {patchMutation.isError &&
            `Не удалось сохранить: ${patchMutation.error.message}. `}
          {designMutation.isError &&
            `Оформление не удалось: ${designMutation.error.message}. `}
          {enrichMutation.isError &&
            `Обновление не удалось: ${enrichMutation.error.message}. `}
          {deleteMutation.isError &&
            `Удаление не удалось: ${deleteMutation.error.message}.`}
        </p>
      )}

      <div className="detail-top">
        <div className="detail-cover">
          {book.cover_url ? (
            <img src={book.cover_url} alt={`Обложка книги «${book.title}»`} />
          ) : (
            <div className="cover-empty">Нет обложки</div>
          )}
        </div>

        <div className="detail-info">
          <h1 className="detail-title">{book.title}</h1>
          <p className="detail-author">{book.author}</p>
          {book.enrich_status === "pending" && (
            <p className="muted">Обложка и описание подгружаются…</p>
          )}
          {book.enrich_status === "failed" && (
            <p className="error">
              Не удалось получить данные о книге — нажмите «Обновить
              информацию».
            </p>
          )}
          {design && <p className="detail-statement">{design.statement}</p>}

          <div className="status-row" role="group" aria-label="Статус чтения">
            {STATUSES.map((s) => (
              <button
                key={s}
                className={"pill " + (book.status === s ? "pill-active" : "")}
                onClick={() => patchMutation.mutate({ status: s })}
                disabled={saving}
                aria-pressed={book.status === s}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>

          {book.status === "read" && (
            <div className="rating-row">
              <label className="rating-label" htmlFor="rating-select">
                Оценка:
              </label>
              <select
                id="rating-select"
                value={book.rating ?? ""}
                onChange={(e) =>
                  patchMutation.mutate({ rating: Number(e.target.value) })
                }
                disabled={saving}
              >
                <option value="" disabled>
                  —
                </option>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {book.description && (
        <p className="detail-description">{book.description}</p>
      )}

      <AtmosphereSection bookId={book.id} category="music" />
    </div>
  );
}

export default BookDetail;
