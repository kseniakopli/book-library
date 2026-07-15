import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";

const STATUS_LABELS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

const STATUSES = ["want", "reading", "read"];

function BookDetail({ book, onBack, onDeleted }) {
  const queryClient = useQueryClient();
  const [activeSource, setActiveSource] = useState("Claude");

  // --- Данные: музыка и паспорт оформления (кэшируются по id книги) ---
  const {
    data: musicData,
    isLoading: musicLoading,
    isError: musicError,
    refetch: refetchMusic,
  } = useQuery({
    queryKey: ["music", book.id],
    queryFn: () => api.getMusic(book.id),
  });
  const selections = musicData?.selections ?? [];

  // Паспорт без обработки ошибки: не загрузился — карточка в базовой теме
  const { data: designData } = useQuery({
    queryKey: ["design", book.id],
    queryFn: () => api.getDesign(book.id),
  });
  const design = designData?.design ?? null;

  // --- Мутации ---
  const patchMutation = useMutation({
    mutationFn: (body) => api.patchBook({ id: book.id, ...body }),
    // инвалидация по префиксу ["books"]: обновятся и список, и эта карточка
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books"] }),
  });
  const saving = patchMutation.isPending;

  const musicMutation = useMutation({
    mutationFn: () => api.generateMusic(book.id),
    // POST возвращает тот же формат, что GET — кладём ответ прямо в кэш без перезапроса
    onSuccess: (data) => queryClient.setQueryData(["music", book.id], data),
  });

  const designMutation = useMutation({
    mutationFn: () => api.generateDesign(book.id),
    // а тут формат ответа POST отличается от GET — проще перезапросить
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["design", book.id] }),
  });

  const enrichMutation = useMutation({
    mutationFn: () => api.enrichBook(book.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteBook(book.id),
    onSuccess: onDeleted, // App: инвалидация + возврат на главную
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

  // Подключаем шрифты из паспорта (Google Fonts)
  useEffect(() => {
    if (!design) return;
    const families = [design.title_font, design.body_font]
      .map((f) => f.trim().replace(/ /g, "+"))
      .join("&family=");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${families}&display=swap`;
    document.head.appendChild(link);
    return () => document.head.removeChild(link);
  }, [design]);

  const active = selections.find((s) => s.source === activeSource);

  // Паспорт → CSS-переменные и шрифты (наследуются всеми детьми карточки)
  const themedStyle = design
    ? {
        "--surface": design.palette.surface,
        "--accent": design.palette.accent,
        "--text": design.palette.text,
        "--muted": design.palette.muted,
        "--border": design.palette.muted,
        "--serif": `'${design.title_font}', Georgia, serif`,
        background: design.palette.bg,
        color: design.palette.text,
        fontFamily: `'${design.body_font}', system-ui, sans-serif`,
        padding: "28px",
        borderRadius: "16px",
      }
    : {};

  return (
    <div className="detail" style={themedStyle}>
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
            <img src={book.cover_url} alt={book.title} />
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

          <div className="status-row">
            {STATUSES.map((s) => (
              <button
                key={s}
                className={"pill " + (book.status === s ? "pill-active" : "")}
                onClick={() => patchMutation.mutate({ status: s })}
                disabled={saving}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>

          {book.status === "read" && (
            <div className="rating-row">
              <span className="rating-label">Оценка:</span>
              <select
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

      <section className="atmosphere">
        <div className="atmosphere-head">
          <h2 className="atmosphere-title">Атмосфера · Музыка</h2>
          <button
            className="add-btn"
            onClick={() => musicMutation.mutate()}
            disabled={musicMutation.isPending}
          >
            {musicMutation.isPending
              ? "Подбираю…"
              : selections.length
                ? "Обновить"
                : "Подобрать музыку"}
          </button>
        </div>

        {musicLoading && <p className="muted">Загружаю подборку…</p>}

        {musicError && (
          <p className="error">
            Не удалось загрузить подборку.{" "}
            <button className="btn-ghost" onClick={() => refetchMusic()}>
              Повторить
            </button>
          </p>
        )}

        {musicMutation.isPending && (
          <p className="muted">Claude и ChatGPT подбирают музыку…</p>
        )}

        {musicMutation.isError && (
          <p className="error">
            Не удалось подобрать музыку: {musicMutation.error.message}
          </p>
        )}

        {!musicLoading &&
          !musicError &&
          !musicMutation.isPending &&
          selections.length === 0 && (
            <p className="muted">
              Пока нет подборки. Нажмите «Подобрать музыку».
            </p>
          )}

        {selections.length > 0 && (
          <>
            <div className="source-tabs">
              {selections.map((s) => (
                <button
                  key={s.source}
                  className={
                    "pill " + (activeSource === s.source ? "pill-active" : "")
                  }
                  onClick={() => setActiveSource(s.source)}
                >
                  {s.source}
                </button>
              ))}
            </div>

            {active && (
              <>
                <p className="atmosphere-explanation">{active.explanation}</p>
                <ol className="songs">
                  {active.songs.map((song, i) => (
                    <li className="song" key={i}>
                      <span className="song-title">{song.title}</span>
                      <span className="song-artist">{song.artist}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

export default BookDetail;
