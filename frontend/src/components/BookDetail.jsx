// Страница книги: композиция блоков. Логика паспорта — в хуке useBookDesign,
// действия/статусы/плейлист — в отдельных компонентах (ревью 19.07).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import { useBookDesign } from "../hooks/useBookDesign";
import AtmosphereSection from "./AtmosphereSection";
import BookActionsBar from "./BookActionsBar";
import BookStatusRow from "./BookStatusRow";
import EditBookModal from "./EditBookModal";
import SpotifyPlaylistBlock from "./SpotifyPlaylistBlock";
import { SkeletonText } from "./Skeleton";

function BookDetail({ book, onBack, onDeleted }) {
  const queryClient = useQueryClient();
  const { theme } = useTheme();
  const [showEdit, setShowEdit] = useState(false);   // задача 3: ручная правка

  const {
    design,
    appliedDesign,
    themedStyle,
    symbolUri,
    symbolOk,
    onSymbolError,
    generating: designGenerating,
    generationError: designError,
  } = useBookDesign(book.id, theme);

  // обложка может не загрузиться (битая ссылка) — откатываемся на символ/заглушку
  const [coverBroken, setCoverBroken] = useState(false);
  const coverOk = book.cover_url && !coverBroken;

  // Кнопка Spotify доступна, только когда музыка подобрана — плейлист собирается
  // из неё. Ключ кэша общий с AtmosphereSection, лишнего запроса нет.
  const { data: musicData } = useQuery({
    queryKey: keys.atmosphere(book.id, "music"),
    queryFn: () => api.getAtmosphere(book.id, "music"),
  });
  const hasMusic = (musicData?.selections?.length ?? 0) > 0;

  const patchMutation = useMutation({
    mutationFn: (body) => api.patchBook({ id: book.id, ...body }),
    // инвалидация по префиксу keys.books: обновятся и список, и эта карточка
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });

  const enrichMutation = useMutation({
    mutationFn: () => api.enrichBook(book.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.books }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteBook(book.id),
    onSuccess: onDeleted,   // BookPage: инвалидация + возврат на главную
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

  const errors = [
    patchMutation.isError && `Не удалось сохранить: ${patchMutation.error.message}.`,
    designError &&
      `Оформление не подобралось: ${designError.message} — попробуйте перезагрузить страницу.`,
    enrichMutation.isError && `Обновление не удалось: ${enrichMutation.error.message}.`,
    deleteMutation.isError && `Удаление не удалось: ${deleteMutation.error.message}.`,
  ].filter(Boolean);

  return (
    <div
      className={"detail" + (appliedDesign ? " detail-themed" : "")}
      style={themedStyle}
    >
      <BookActionsBar
        bookId={book.id}
        onBack={onBack}
        onEnrich={() => enrichMutation.mutate()}
        enriching={enrichMutation.isPending}
        onEdit={() => setShowEdit(true)}
        onDelete={removeBook}
        deleting={deleteMutation.isPending}
      />

      {errors.length > 0 && <p className="error">{errors.join(" ")}</p>}

      {/* Задача 46: две колонки — информация слева (sticky), атмосфера справа */}
      <div className="detail-columns">
        <div className="detail-main">
          <div className="detail-top">
            <div className="detail-cover">
              {coverOk ? (
                <img
                  src={book.cover_url}
                  alt={`Обложка книги «${book.title}»`}
                  onError={() => setCoverBroken(true)}
                />
              ) : symbolOk ? (
                // задача 50: вместо «Нет обложки» — символ-экслибрис книги
                <div className="cover-empty cover-symbol">
                  <img src={symbolUri} alt="" aria-hidden="true" onError={onSymbolError} />
                </div>
              ) : (
                <div className="cover-empty">Нет обложки</div>
              )}
            </div>

            <div className="detail-info">
              <div className="detail-title-row">
                {symbolOk && (
                  <img
                    className="book-symbol"
                    src={symbolUri}
                    alt=""
                    aria-hidden="true"
                    onError={onSymbolError}
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
              {designGenerating && (
                <div className="detail-statement">
                  <SkeletonText lines={2} />
                </div>
              )}
              {design && <p className="detail-statement">{design.statement}</p>}

              <BookStatusRow
                book={book}
                onChange={(body) => patchMutation.mutate(body)}
                saving={patchMutation.isPending}
              />

              <SpotifyPlaylistBlock book={book} hasMusic={hasMusic} />
            </div>
          </div>

          {book.description && (
            <p className="detail-description">{book.description}</p>
          )}
        </div>

        <AtmosphereSection bookId={book.id} />
      </div>

      {showEdit && (
        <EditBookModal book={book} onClose={() => setShowEdit(false)} />
      )}
    </div>
  );
}

export default BookDetail;
