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
// Пауза перед отправкой: выбор нескольких жанров подряд — это один заход,
// а не пять. Короче секунды, чтобы человек не успел уйти со страницы.
const SAVE_DELAY_MS = 600;

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

  const genres = data?.genres ?? [];
  const [draft, setDraft] = useState(EMPTY);
  // Есть ли правка, ещё не доехавшая до сервера. ⚠ Нужен, чтобы ответ
  // запроса не затёр только что сделанный выбор: чекбокс рисуется сразу,
  // а данные приходят позже (страница за `React.lazy`).
  const pending = useRef(false);
  const timer = useRef(null);

  // подтягиваем сохранённое, когда запрос ответил, но НЕ поверх того,
  // что человек уже нажал
  useEffect(() => {
    if (!pending.current) setDraft(data?.settings ?? EMPTY);
  }, [data?.settings]);

  const save = useMutation({
    // значение передаём явно, а не берём из замыкания: к моменту отправки
    // `draft` уже может смениться следующим кликом
    mutationFn: (value) => api.saveRecommendationSettings(value),
    onSuccess: (fresh) => {
      pending.current = false;
      queryClient.setQueryData(keys.recommendations, (old) =>
        old ? { ...old, settings: fresh.settings } : old,
      );
    },
  });

  /** Правка сохраняется САМА (правка 06.08).
   *
   *  ⚠ Раньше здесь был черновик и кнопка «Сохранить настройки». Ксения
   *  отметила жанры, нажала «Обновить» — и получила подбор по старым
   *  настройкам: на экране выбор выглядел применённым, а в базе его не было
   *  (`genre_asked: 0` в событии). Кнопка рядом с действием, которое читает
   *  СОХРАНЁННОЕ, — это ловушка, а не свобода.
   *  Лечим не предупреждением, а тем, что несохранённого состояния больше
   *  не существует (`Уроки.md` 1.1: убирать возможность ошибки).
   *
   *  Задержка — чтобы выбор пяти жанров подряд не дал пять запросов;
   *  последний клик отменяет предыдущий таймер. */
  const edit = (next) => {
    pending.current = true;
    setDraft(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => save.mutate(next), SAVE_DELAY_MS);
  };

  // уход со страницы посреди задержки не должен терять правку
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const toggle = (field) => (slug) =>
    edit({
      ...draft,
      [field]: draft[field].includes(slug)
        ? draft[field].filter((s) => s !== slug)
        : [...draft[field], slug],
    });

  return (
    <section className="rec-settings">
      <div className="rec-settings-head">
        <h2 className="rec-settings-title">Настройки подбора</h2>
        {/* Без кнопки человеку неоткуда узнать, что правка дошла, —
            поэтому состояние показываем явно. «Сохраняются сразу» стоит
            и в покое: это обещание, а не отчёт о последнем действии. */}
        <span className="stat-hint rec-settings-status" aria-live="polite">
          {save.isPending
            ? "Сохраняю…"
            : save.isError
              ? "Не сохранилось — проверьте связь"
              : "Изменения сохраняются сразу"}
        </span>
      </div>

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

      {save.isError && (
        <p className="error rec-settings-error">
          Не удалось сохранить настройки: {save.error.message}. Подбор пойдёт
          по прежним — нажмите любой жанр ещё раз.
        </p>
      )}
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
