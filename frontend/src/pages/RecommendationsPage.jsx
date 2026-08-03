// Рекомендации отдельной страницей (задача 110).
//
// Раньше это была третья полка на главной. Уехала сюда по двум причинам:
// главная перегружена, а сами советы — не то, что смотрят при каждом заходе.
// ⚠ Первый заход даёт пустой экран с кнопкой генерации — принято осознанно
// (решение Ксении): подбор тратит токены, и запускать его автоматически
// при открытии страницы значит платить за каждый случайный клик по меню.
// Со временем страница обрастёт настройками пожеланий (задача 114).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import RecommendationShelf from "../components/RecommendationShelf";

const MAX_WISHES = 500;

/** Пожелания словами (задача 114).
 *
 *  Тот же механизм, что профиль вкуса по 👍/👎, только вход не кнопками,
 *  а текстом. Живёт НАД полкой: это настройка того, что появится ниже,
 *  и читать её после списка советов бессмысленно. */
function Wishes() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: keys.recommendations,
    queryFn: api.getRecommendations,
  });
  const saved = data?.wishes ?? "";
  const [draft, setDraft] = useState(saved);

  // подтягиваем сохранённое, когда запрос ответил (первый рендер идёт без него)
  useEffect(() => setDraft(saved), [saved]);

  const save = useMutation({
    mutationFn: () => api.saveWishes(draft),
    onSuccess: (fresh) => {
      // бэкенд возвращает ОЧИЩЕННЫЙ текст: в базе лежит ровно то, что уедет
      // модели, и поле должно показывать его же, а не наш черновик
      queryClient.setQueryData(keys.recommendations, (old) =>
        old ? { ...old, wishes: fresh.wishes } : old,
      );
    },
  });

  const changed = draft !== saved;

  return (
    <section className="wishes">
      <h2 className="wishes-title">Пожелания</h2>
      <p className="muted">
        Напишите словами, чего не хотите и что любите: «не люблю антиутопии»,
        «больше северного нуара». Это уйдёт в подбор вместе с вашими оценками.
      </p>
      <textarea
        className="wishes-input"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        maxLength={MAX_WISHES}
        aria-label="Пожелания для рекомендаций"
        placeholder="Например: не предлагай антиутопии и книги о войне"
      />
      <div className="wishes-actions">
        <button
          className="btn-ghost"
          onClick={() => save.mutate()}
          disabled={!changed || save.isPending}
        >
          {save.isPending ? "Сохраняю…" : "Сохранить пожелания"}
        </button>
        <span className="stat-hint">
          {draft.length}/{MAX_WISHES}
        </span>
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
        Советы новых книг по вашим оценкам от 7 и выше. Claude и ChatGPT
        предлагают по пять каждый, совпавшие книги схлопываются.
      </p>

      <Wishes />

      {/* на своей странице полка — главный блок, поэтому её заголовок h1 */}
      <RecommendationShelf heading="h1" />
    </div>
  );
}

export default RecommendationsPage;
