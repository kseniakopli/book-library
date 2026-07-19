// Полка «Рекомендации» (этап 8): книги, которых в библиотеке ещё нет.
// Подбираются по кнопке (тратит токены), хранятся на бэкенде до следующей
// генерации. Клик по карточке добавляет книгу в «Хочу прочитать».
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { SkeletonRows } from "./Skeleton";

function RecommendationShelf() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: keys.recommendations,
    queryFn: api.getRecommendations,
  });
  const items = data?.recommendations ?? [];
  const noFavorites = data?.detail === "no_favorites";

  const generate = useMutation({
    mutationFn: api.generateRecommendations,
    onSuccess: (fresh) => queryClient.setQueryData(keys.recommendations, fresh),
  });

  // добавляем совет в библиотеку как «Хочу прочитать»
  const add = useMutation({
    mutationFn: (item) =>
      api.createBook({
        title: item.title,
        author: item.author,
        cover_url: item.cover_url,
        external_id: item.external_id,
        status: "want",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.books });
      // добавленная книга больше не совет — перечитаем полку
      queryClient.invalidateQueries({ queryKey: keys.recommendations });
    },
  });

  return (
    <section className="shelf">
      <div className="shelf-head">
        <h2 className="shelf-title">
          Рекомендации{" "}
          {items.length > 0 && <span className="shelf-count">{items.length}</span>}
        </h2>
        <button
          className={items.length > 0 ? "btn-ghost" : "add-btn"}
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
        >
          {generate.isPending
            ? "Подбираю…"
            : items.length > 0
              ? "Обновить"
              : "Подобрать рекомендации"}
        </button>
      </div>

      {generate.isPending && <SkeletonRows rows={3} />}

      {generate.isError && (
        <p className="error">
          Не удалось подобрать: {generate.error.message}
        </p>
      )}

      {!generate.isPending && !isLoading && items.length === 0 && (
        <p className="shelf-placeholder">
          {noFavorites
            ? "Пока не по чему советовать: поставьте оценки прочитанным книгам (от 7), и я подберу похожее."
            : "Нажмите «Подобрать рекомендации» — предложу книги по вашим любимым."}
        </p>
      )}

      {items.length > 0 && (
        <ul className="rec-list">
          {items.map((item, i) => (
            <li className="rec-card" key={`${item.title}-${i}`}>
              <div className="rec-cover">
                {item.cover_url ? (
                  <img src={item.cover_url} alt="" loading="lazy" />
                ) : (
                  <span className="rec-cover-empty">Нет обложки</span>
                )}
              </div>
              <div className="rec-text">
                <h3 className="rec-title">{item.title}</h3>
                <p className="rec-author">{item.author}</p>
                <p className="rec-reason">{item.reason}</p>
              </div>
              <button
                className="btn-ghost rec-add"
                onClick={() => add.mutate(item)}
                disabled={add.isPending}
              >
                + В «Хочу прочитать»
              </button>
            </li>
          ))}
        </ul>
      )}

      {add.isError && (
        <p className="error">Не удалось добавить: {add.error.message}</p>
      )}
    </section>
  );
}

export default RecommendationShelf;
