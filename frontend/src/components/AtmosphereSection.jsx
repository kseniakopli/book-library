// Секция «Атмосфера» для списочных категорий (music; этап 7: food, aroma).
// Выделена из BookDetail (R7): добавление категории = запись в COPY +
// рендер payload в renderPayload.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

const COPY = {
  music: {
    heading: "Атмосфера · Музыка",
    generate: "Подобрать музыку",
    regenerate: "Обновить",
    pending: "Claude и ChatGPT подбирают музыку…",
    loading: "Загружаю подборку…",
    empty: "Пока нет подборки. Нажмите «Подобрать музыку».",
    error: "Не удалось подобрать музыку",
    loadError: "Не удалось загрузить подборку.",
  },
  // этап 7: food: {...}, aroma: {...}
};

// payload зависит от категории: для музыки это список {title, artist}
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
  return null;
}

function AtmosphereSection({ bookId, category }) {
  const queryClient = useQueryClient();
  const [activeSource, setActiveSource] = useState("Claude");
  const copy = COPY[category];

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: keys.atmosphere(bookId, category),
    queryFn: () => api.getAtmosphere(bookId, category),
  });
  const selections = data?.selections ?? [];

  const generateMutation = useMutation({
    mutationFn: () => api.generateAtmosphere(bookId, category),
    // POST возвращает тот же формат, что GET — кладём ответ прямо в кэш
    onSuccess: (fresh) =>
      queryClient.setQueryData(keys.atmosphere(bookId, category), fresh),
  });

  const active = selections.find((s) => s.source === activeSource);

  return (
    <section className="atmosphere">
      <div className="atmosphere-head">
        <h2 className="atmosphere-title">{copy.heading}</h2>
        <button
          className="add-btn"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          {generateMutation.isPending
            ? "Подбираю…"
            : selections.length
              ? copy.regenerate
              : copy.generate}
        </button>
      </div>

      {isLoading && <p className="muted">{copy.loading}</p>}

      {isError && (
        <p className="error">
          {copy.loadError}{" "}
          <button className="btn-ghost" onClick={() => refetch()}>
            Повторить
          </button>
        </p>
      )}

      {generateMutation.isPending && <p className="muted">{copy.pending}</p>}

      {generateMutation.isError && (
        <p className="error">
          {copy.error}: {generateMutation.error.message}
        </p>
      )}

      {!isLoading &&
        !isError &&
        !generateMutation.isPending &&
        selections.length === 0 && <p className="muted">{copy.empty}</p>}

      {selections.length > 0 && (
        <>
          <div
            className="source-tabs"
            role="group"
            aria-label="Источник подборки"
          >
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
              {renderPayload(category, active.payload)}
            </>
          )}
        </>
      )}
    </section>
  );
}

export default AtmosphereSection;
