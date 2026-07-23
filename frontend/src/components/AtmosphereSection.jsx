// Единая панель «Атмосфера»: одна кнопка генерирует все категории разом,
// вкладки категорий (Музыка / Угощения / Ароматы), внутри — источники.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { SkeletonRows } from "./Skeleton";
import FeedbackButtons from "./FeedbackButtons";

const CATEGORIES = [
  { id: "music", label: "Музыка" },
  { id: "food", label: "Угощения" },
  { id: "aroma", label: "Ароматы" },
];
const CATEGORY_IDS = CATEGORIES.map((c) => c.id);

// payload зависит от категории: музыка — {title, artist}, остальные — {title, description}
// onRemoveTrack — точечное удаление трека (admin-действие; UI-скрытие для
// не-админов отложено до авторизации вместе с остальными admin-кнопками, з.31)
function renderPayload(category, payload, onRemoveTrack) {
  if (category === "music") {
    return (
      <ol className="songs">
        {payload.map((song, i) => (
          <li className="song" key={i}>
            <span className="song-title">{song.title}</span>
            <span className="song-artist">{song.artist}</span>
            {onRemoveTrack && (
              <button
                className="song-remove"
                onClick={() => onRemoveTrack(song)}
                aria-label={`Удалить трек ${song.title}`}
                title="Удалить трек из подборки и плейлиста"
              >
                ✕
              </button>
            )}
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ul className="atmosphere-items">
      {payload.map((item, i) => (
        <li className="atmosphere-item" key={i}>
          <span className="atmosphere-item-title">{item.title}</span>
          <span className="atmosphere-item-description">
            {item.description}
          </span>
        </li>
      ))}
    </ul>
  );
}

function AtmosphereSection({ bookId }) {
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState("music");
  const [activeSource, setActiveSource] = useState("Claude");

  // По запросу на категорию — каждый со своим кэшем
  const music = useQuery({
    queryKey: keys.atmosphere(bookId, "music"),
    queryFn: () => api.getAtmosphere(bookId, "music"),
  });
  const food = useQuery({
    queryKey: keys.atmosphere(bookId, "food"),
    queryFn: () => api.getAtmosphere(bookId, "food"),
  });
  const aroma = useQuery({
    queryKey: keys.atmosphere(bookId, "aroma"),
    queryFn: () => api.getAtmosphere(bookId, "aroma"),
  });
  const byCategory = { music, food, aroma };

  // Одна кнопка — все категории параллельно (на бэкенде это 6 AI-вызовов)
  const generateAll = useMutation({
    mutationFn: async () => {
      const results = await Promise.all(
        CATEGORY_IDS.map((c) => api.generateAtmosphere(bookId, c)),
      );
      return Object.fromEntries(CATEGORY_IDS.map((c, i) => [c, results[i]]));
    },
    onSuccess: (fresh) => {
      for (const c of CATEGORY_IDS) {
        queryClient.setQueryData(keys.atmosphere(bookId, c), fresh[c]);
      }
      // вместе с музыкой бэкенд собирает Spotify-плейлист (20.07) — перечитываем
      // книгу, чтобы кнопка сменилась на «Открыть плейлист»
      queryClient.invalidateQueries({ queryKey: keys.book(bookId) });
    },
  });

  // Удаление одного трека: точечно дешевле, чем перегенерация всей музыки.
  // Бэкенд убирает трек из подборки и пересобирает Spotify-плейлист.
  const removeTrack = useMutation({
    mutationFn: ({ title, artist }) =>
      api.removeTrack({ id: bookId, source: activeSource, title, artist }),
    onSuccess: (fresh) => {
      queryClient.setQueryData(keys.atmosphere(bookId, "music"), fresh);
    },
  });

  const current = byCategory[activeCategory];
  const selections = current.data?.selections ?? [];
  const active = selections.find((s) => s.source === activeSource);
  const hasAny = CATEGORY_IDS.some(
    (c) => (byCategory[c].data?.selections?.length ?? 0) > 0,
  );

  return (
    <section className="atmosphere">
      <div className="atmosphere-head">
        <h2 className="atmosphere-title">Атмосфера</h2>
        {/* задача 47: accent — только пока атмосферы нет (главное действие
            страницы); повторная генерация — обычная кнопка */}
        <button
          className={hasAny ? "btn-ghost" : "add-btn"}
          onClick={() => generateAll.mutate()}
          disabled={generateAll.isPending}
        >
          {generateAll.isPending
            ? "Подбираю…"
            : hasAny
              ? "Обновить атмосферу"
              : "Подобрать атмосферу"}
        </button>
      </div>

      <div
        className="category-tabs"
        role="group"
        aria-label="Категория атмосферы"
      >
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            className={
              "category-tab" + (activeCategory === c.id ? " active" : "")
            }
            onClick={() => setActiveCategory(c.id)}
            aria-pressed={activeCategory === c.id}
          >
            {c.label}
          </button>
        ))}
      </div>

      {generateAll.isPending && (
        <>
          <p className="muted">Claude и ChatGPT собирают атмосферу вечера…</p>
          <SkeletonRows rows={5} />
        </>
      )}
      {generateAll.isError && (
        <p className="error">
          Не удалось подобрать атмосферу: {generateAll.error.message}
        </p>
      )}

      {current.isLoading && !generateAll.isPending && <SkeletonRows rows={4} />}
      {current.isError && (
        <p className="error">
          Не удалось загрузить подборку.{" "}
          <button className="btn-ghost" onClick={() => current.refetch()}>
            Повторить
          </button>
        </p>
      )}

      {!current.isLoading &&
        !current.isError &&
        !generateAll.isPending &&
        selections.length === 0 && (
          <p className="muted">
            Пока пусто. Нажмите «Подобрать атмосферу» — музыка, угощения и
            ароматы подберутся разом.
          </p>
        )}

      {selections.length > 0 && (
        <>
          <div
            className="source-tabs"
            role="group"
            aria-label="Источник подборки"
          >
            <span className="source-label">Вариант:</span>
            {selections.map((s) => (
              <button
                key={s.source}
                className={
                  "pill " + (activeSource === s.source ? "pill-active" : "")
                }
                onClick={() => setActiveSource(s.source)}
                aria-pressed={activeSource === s.source}
              >
                {s.source}
              </button>
            ))}
          </div>

          {/* задача 85: музыка сохранена при недоступном Spotify — треки не
              проверены, плейлиста нет; соберётся при следующей генерации */}
          {activeCategory === "music" && current.data?.verified === false && (
            <p className="muted">
              Spotify был недоступен — треки не проверены и плейлист не собран.
              Нажмите «Обновить атмосферу», когда Spotify снова заработает.
            </p>
          )}

          {active && (
            <>
              <div className="atmosphere-explanation-row">
                <p className="atmosphere-explanation">{active.explanation}</p>
                {/* оценка подборки этой категории от этого источника */}
                <FeedbackButtons
                  refKey={`atmosphere:${bookId}:${activeCategory}:${active.source}`}
                  source={active.source}
                />
              </div>
              {removeTrack.isError && (
                <p className="error">
                  Не удалось удалить трек: {removeTrack.error.message}
                </p>
              )}
              {renderPayload(
                activeCategory,
                active.payload,
                activeCategory === "music"
                  ? (song) => !removeTrack.isPending && removeTrack.mutate(song)
                  : undefined,
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}

export default AtmosphereSection;
