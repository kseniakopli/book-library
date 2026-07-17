// Карточка книги: паспорт оформления, статус/оценка, действия.
// Секция «Атмосфера» вынесена в AtmosphereSection (R7).
import { useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { STATUS_LABELS, STATUSES } from "../constants";
import { useTheme } from "../hooks/useTheme";
import { bestTextOn, hasReadableContrast, withAlpha } from "../lib/contrast";
import { centeredSvgDataUri } from "../lib/svg";
import AtmosphereSection from "./AtmosphereSection";

function BookDetail({ book, onBack, onDeleted }) {
  const queryClient = useQueryClient();
  const { theme } = useTheme();

  // Паспорт оформления: единый формат атмосферы, паспорт — payload единственного источника.
  // Без обработки ошибки: не загрузился — карточка в базовой теме.
  const { data: designData } = useQuery({
    queryKey: keys.atmosphere(book.id, "design"),
    queryFn: () => api.getAtmosphere(book.id, "design"),
  });
  const design = designData?.selections?.[0]?.payload ?? null;

  // Символ: перецентровка viewBox по реальным границам рисунка (мемо —
  // внутри есть работа с DOM, незачем повторять на каждый рендер)
  const symbolUri = useMemo(
    () => (design?.symbol_svg ? centeredSvgDataUri(design.symbol_svg) : null),
    [design?.symbol_svg],
  );

  // Задача 57: палитра выбирается по теме интерфейса. Новый формат паспорта —
  // palette_dark + palette_light; старый (одно поле palette) считаем тёмным.
  const palette = design
    ? theme === "dark"
      ? (design.palette_dark ?? design.palette)
      : design.palette_light
    : null;

  // Задача 23: применяем AI-палитру, только если текст читаем на её фоне (WCAG AA).
  const appliedDesign =
    design && palette && hasReadableContrast(palette.text, palette.bg)
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

  // Задача 57: оформление без кнопки. Паспорта нет (книга из CSV/старая,
  // или фон при добавлении не успел/упал) либо он старого формата без
  // светлой палитры — тихо генерируем один раз при открытии.
  const designAutoFired = useRef(false);
  const designMutate = designMutation.mutate;
  useEffect(() => {
    if (!designData || designAutoFired.current) return;
    if (!design || !design.palette_light) {
      designAutoFired.current = true;
      designMutate();
    }
  }, [designData, design, designMutate]);

  const enrichMutation = useMutation({
    mutationFn: () => api.enrichBook(book.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteBook(book.id),
    onSuccess: onDeleted, // BookPage: инвалидация + возврат на главную
  });

  // Spotify-плейлист (этап 10.2): первый раз откроется окно авторизации Spotify,
  // после него плейлисты создаются в один клик
  const playlistMutation = useMutation({
    mutationFn: () => api.createPlaylist(book.id),
    onSuccess: (data) => {
      if (data.status === "auth_required") {
        window.open(data.auth_url, "_blank", "noopener");
        return;
      }
      queryClient.invalidateQueries({ queryKey: keys.books });
    },
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
        "--surface": palette.surface,
        "--accent": palette.accent,
        // задача 49: текст на accent — вычисляем по контрасту (тема сюда не дотягивается)
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
          <Link className="btn-ghost playlist-link" to={`/books/${book.id}/card`}>
            Печатная карточка
          </Link>
          <button
            className="btn-danger"
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
            `Оформление не подобралось: ${designMutation.error.message} — попробуйте перезагрузить страницу. `}
          {enrichMutation.isError &&
            `Обновление не удалось: ${enrichMutation.error.message}. `}
          {deleteMutation.isError &&
            `Удаление не удалось: ${deleteMutation.error.message}.`}
        </p>
      )}

      {/* Задача 46: две колонки — информация слева (sticky), атмосфера справа */}
      <div className="detail-columns">
        <div className="detail-main">
          <div className="detail-top">
            <div className="detail-cover">
          {book.cover_url ? (
            <img src={book.cover_url} alt={`Обложка книги «${book.title}»`} />
          ) : symbolUri ? (
            // задача 50: вместо «Нет обложки» — символ-экслибрис книги
            <div className="cover-empty cover-symbol">
              <img src={symbolUri} alt="" aria-hidden="true" />
            </div>
          ) : (
            <div className="cover-empty">Нет обложки</div>
          )}
        </div>

        <div className="detail-info">
          <div className="detail-title-row">
            {symbolUri && (
              <img
                className="book-symbol"
                src={symbolUri}
                alt=""
                aria-hidden="true"
              />
            )}
            <div className="detail-title-text">
              <h1 className="detail-title">{book.title}</h1>
              <p className="detail-author">{book.author}</p>
            </div>
          </div>
          {book.enrich_status === "pending" && (
            <p className="muted">Обложка и описание подгружаются…</p>
          )}
          {book.enrich_status === "failed" && (
            <p className="error">
              Не удалось получить данные о книге — нажмите «Обновить
              информацию».
            </p>
          )}
          {designMutation.isPending && (
            <p className="muted">Подбираю оформление под книгу…</p>
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

          {(book.status === "read" || book.external_rating != null) && (
            <div className="rating-row">
              {book.status === "read" && (
                <>
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
                </>
              )}
              {book.external_rating != null && (
                <span
                  className="rating-badge"
                  title="Средний рейтинг Google Books (шкала 1–5)"
                >
                  ★ {String(book.external_rating.toFixed(1)).replace(".", ",")}{" "}
                  · Google
                </span>
              )}
            </div>
          )}

          <div className="playlist-row">
            {book.spotify_playlist_url ? (
              <a
                className="btn-ghost playlist-link"
                href={book.spotify_playlist_url}
                target="_blank"
                rel="noreferrer"
              >
                ♫ Открыть плейлист в Spotify
              </a>
            ) : (
              <button
                className="btn-ghost"
                onClick={() => playlistMutation.mutate()}
                disabled={playlistMutation.isPending}
              >
                {playlistMutation.isPending
                  ? "Создаю плейлист…"
                  : "♫ Создать плейлист в Spotify"}
              </button>
            )}
          </div>
          {playlistMutation.data?.status === "auth_required" && (
            <p className="muted">
              Разрешите доступ в открывшемся окне Spotify — плейлист создастся
              автоматически.
            </p>
          )}
          {playlistMutation.data?.not_found?.length > 0 && (
            <p className="muted">
              Не нашлись в Spotify:{" "}
              {playlistMutation.data.not_found.join(", ")}
            </p>
          )}
          {playlistMutation.isError && (
            <p className="error">
              Плейлист не создался: {playlistMutation.error.message}
            </p>
          )}
        </div>
      </div>

          {book.description && (
            <p className="detail-description">{book.description}</p>
          )}
        </div>

        <AtmosphereSection bookId={book.id} />
      </div>
    </div>
  );
}

export default BookDetail;
