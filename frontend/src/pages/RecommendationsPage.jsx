// Рекомендации отдельной страницей (задача 110).
//
// Раньше это была третья полка на главной. Уехала сюда по двум причинам:
// главная перегружена, а сами советы — не то, что смотрят при каждом заходе.
// ⚠ Первый заход даёт пустой экран с кнопкой генерации — принято осознанно
// (решение Ксении): подбор тратит токены, и запускать его автоматически
// при открытии страницы значит платить за каждый случайный клик по меню.
//
// Задача 124 (06.08): пожелания СЛОВАМИ (з.114) заменены настройками.
// Свободный текст было непонятно, как исполнять, и проверить исполнение
// нечем. Настройки же либо проверяются кодом (авторы), либо хотя бы
// формулируются однозначно (жанры).
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import RecommendationShelf from "../components/RecommendationShelf";

const EMPTY = { skip_known_authors: false, genres_include: [], genres_exclude: [] };

/** Список жанров с множественным выбором.
 *
 *  Чипы, а не `<select multiple>`: последний на телефоне превращается
 *  в неудобный барабан, а с ctrl+клик на десктопе легко случайно сбросить
 *  весь выбор. Здесь каждый жанр — самостоятельная кнопка-переключатель. */
function GenrePicker({ label, hint, genres, picked, onToggle, disabledSlugs }) {
  return (
    <div className="rec-picker">
      <span className="rec-picker-label">{label}</span>
      <p className="stat-hint rec-picker-hint">{hint}</p>
      <ul className="rec-picker-list">
        {genres.map((genre) => {
          const active = picked.includes(genre.slug);
          // жанр, выбранный в противоположном списке: показываем, но нажать
          // нельзя — «хочу» и «не хочу» одновременно это не выбор, а ошибка
          const blocked = !active && disabledSlugs.includes(genre.slug);
          return (
            <li key={genre.slug}>
              <button
                type="button"
                className={"pill" + (active ? " pill-active" : "")}
                onClick={() => onToggle(genre.slug)}
                disabled={blocked}
                aria-pressed={active}
                title={blocked ? "Уже выбран в другом списке" : undefined}
              >
                {genre.name}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Настройки подбора (задача 124). Живут НАД полкой: это настройка того,
 *  что появится ниже, и читать её после списка советов бессмысленно. */
function Settings() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: keys.recommendations,
    queryFn: api.getRecommendations,
  });

  const saved = data?.settings ?? EMPTY;
  const genres = data?.genres ?? [];
  const [draft, setDraft] = useState(saved);
  // Тронул ли пользователь форму. ⚠ Без этого признака клик, сделанный ДО
  // ответа сервера, молча пропадал: чекбокс рисуется сразу, ответ приходит
  // позже, и `useEffect` затирал им черновик. Поймал тест, но случай живой —
  // страница за `React.lazy`, запрос уходит после загрузки чанка.
  const touched = useRef(false);

  // подтягиваем сохранённое, когда запрос ответил (первый рендер идёт без него),
  // но НЕ поверх несохранённых изменений
  useEffect(() => {
    if (!touched.current) setDraft(data?.settings ?? EMPTY);
  }, [data?.settings]);

  const edit = (next) => {
    touched.current = true;
    setDraft(next);
  };

  const save = useMutation({
    mutationFn: () => api.saveRecommendationSettings(draft),
    onSuccess: (fresh) => {
      touched.current = false;   // сохранили — снова следуем за сервером
      queryClient.setQueryData(keys.recommendations, (old) =>
        old ? { ...old, settings: fresh.settings } : old,
      );
    },
  });

  const toggle = (field) => (slug) =>
    edit({
      ...draft,
      [field]: draft[field].includes(slug)
        ? draft[field].filter((s) => s !== slug)
        : [...draft[field], slug],
    });

  const changed = JSON.stringify(draft) !== JSON.stringify(saved);

  return (
    <section className="rec-settings">
      <h2 className="rec-settings-title">Настройки подбора</h2>

      <label className="rec-check">
        <input
          type="checkbox"
          checked={draft.skip_known_authors}
          onChange={(e) =>
            edit({ ...draft, skip_known_authors: e.target.checked })
          }
        />
        <span>
          Не рекомендовать авторов из библиотеки
          <span className="stat-hint rec-check-hint">
            Про знакомого автора вы и так знаете, что хотите прочитать дальше.
            Учитываются все книги с полки — и прочитанные, и отложенные.
          </span>
        </span>
      </label>

      {genres.length > 0 ? (
        <div className="rec-pickers">
          <GenrePicker
            label="Какие жанры рекомендовать"
            hint="Пусто — без пожеланий, советы по всем вашим оценкам."
            genres={genres}
            picked={draft.genres_include}
            onToggle={toggle("genres_include")}
            disabledSlugs={draft.genres_exclude}
          />
          <GenrePicker
            label="Какие жанры не рекомендовать"
            hint="Отмеченное уйдёт в подбор как «этого сейчас не хочется»."
            genres={genres}
            picked={draft.genres_exclude}
            onToggle={toggle("genres_exclude")}
            disabledSlugs={draft.genres_include}
          />
        </div>
      ) : (
        <p className="muted">
          Жанры пока не заведены — проставьте их книгам, и здесь появится выбор.
        </p>
      )}

      <div className="rec-settings-actions">
        <button
          className="btn-ghost"
          onClick={() => save.mutate()}
          disabled={!changed || save.isPending}
        >
          {save.isPending ? "Сохраняю…" : "Сохранить настройки"}
        </button>
        {save.isError && (
          <p className="error">Не удалось сохранить: {save.error.message}</p>
        )}
      </div>
    </section>
  );
}

function RecommendationsPage() {
  return (
    <div className="recommendations-page">
      <Link className="btn-ghost" to="/">
        ← К библиотеке
      </Link>

      <p className="muted recommendations-lead">
        Советы новых книг по вашим оценкам. Claude и ChatGPT предлагают
        по пять каждый, совпавшие книги схлопываются. Книги с оценкой 5–6
        учитываются отдельно — как чтение для отдыха.
      </p>

      <Settings />

      {/* на своей странице полка — главный блок, поэтому её заголовок h1 */}
      <RecommendationShelf heading="h1" />
    </div>
  );
}

export default RecommendationsPage;
