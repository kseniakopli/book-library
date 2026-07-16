// Единая панель «Атмосфера»: одна кнопка генерирует все категории разом,
// вкладки категорий (Музыка / Угощения / Ароматы), внутри — источники.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

const CATEGORIES = [
  { id: "music", label: "Музыка" },
  { id: "food", label: "Угощения" },
  { id: "aroma", label: "Ароматы" },
];
const CATEGORY_IDS = CATEGORIES.map((c) => c.id);

// payload зависит от категории: музыка — {title, artist}, остальные — {title, description}
function renderPayload(category, payload) {
  if (category === "music") {
    return (
      <ol className="songs">
        {payload.map((song, i) => (
          <li className="song" key={i}>
            <span className="song-title">{song.title}</span>
            <span className="song-artist">{song.artist}</span>
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
        <p className="muted">Claude и ChatGPT собирают атмосферу вечера…</p>
      )}
      {generateAll.isError && (
        <p className="error">
          Не удалось подобрать атмосферу: {generateAll.error.message}
        </p>
      )}

      {current.isLoading && <p className="muted">Загружаю подборку…</p>}
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

          {active && (
            <>
              <p className="atmosphere-explanation">{active.explanation}</p>
              {renderPayload(activeCategory, active.payload)}
            </>
          )}
        </>
      )}
    </section>
  );
}

export default AtmosphereSection;
