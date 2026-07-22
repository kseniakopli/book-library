// Полка циклов (задача 89). Элемент полки — цикл, а не книга: карточки крупнее
// книжных, поэтому их помещается меньше. Порядок задаёт бэкенд:
// читаю → прочитано → перестала читать.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { centeredSvgDataUri } from "../lib/svg";
import { SkeletonRows } from "./Skeleton";
import "../styles/series.css";

const STATUS_LABEL = {
  reading: "Читаю",
  read: "Прочитан",
  dropped: "Перестала читать",
};

function SeriesShelf() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [author, setAuthor] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: keys.series,
    queryFn: api.getSeries,
  });
  const items = data?.series ?? [];

  const create = useMutation({
    mutationFn: () => api.createSeries({ name, author }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: keys.series });
      setCreating(false);
      setName("");
      setAuthor("");
      navigate(`/series/${created.id}`); // сразу на страницу — добавлять книги
    },
  });

  return (
    <section className="shelf">
      <div className="shelf-head">
        <h2 className="shelf-title">
          Циклы{" "}
          {items.length > 0 && <span className="shelf-count">{items.length}</span>}
        </h2>
        <button
          className={items.length > 0 ? "btn-ghost" : "add-btn"}
          onClick={() => setCreating((v) => !v)}
        >
          {creating ? "Отмена" : "+ Новый цикл"}
        </button>
      </div>

      {creating && (
        <form
          className="series-create"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <input
            autoFocus
            placeholder="Название цикла"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            placeholder="Автор (необязательно)"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
          />
          <button className="add-btn" type="submit" disabled={create.isPending}>
            {create.isPending ? "Создаю…" : "Создать"}
          </button>
        </form>
      )}
      {create.isError && (
        <p className="error">Не удалось создать: {create.error.message}</p>
      )}

      {isLoading && <SkeletonRows rows={2} />}

      {!isLoading && items.length === 0 && !creating && (
        <p className="shelf-placeholder">
          Циклов пока нет. Создайте цикл и соберите в него книги серии — будет
          видно, на какой книге вы остановились и что читать дальше.
        </p>
      )}

      {items.length > 0 && (
        <ul className="series-list">
          {items.map((s) => (
            <li key={s.id}>
              <button
                className="series-card"
                onClick={() => navigate(`/series/${s.id}`)}
              >
                <span className="series-symbol" aria-hidden="true">
                  {s.design?.symbol_svg ? (
                    <img src={centeredSvgDataUri(s.design.symbol_svg)} alt="" />
                  ) : (
                    // экслибрис цикла ещё не сгенерирован — знак-заглушка
                    <span className="series-symbol-empty">◆</span>
                  )}
                </span>
                <span className="series-body">
                  <span className="series-name">{s.name}</span>
                  {s.author && <span className="series-author">{s.author}</span>}
                  <span className="series-progress">
                    Прочитано {s.progress.read} из {s.progress.total}
                  </span>
                  {s.progress.next_book && s.status !== "read" && (
                    <span className="series-next">
                      Дальше: {s.progress.next_book.title}
                    </span>
                  )}
                </span>
                <span className={`series-status series-status-${s.status}`}>
                  {STATUS_LABEL[s.status] ?? s.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default SeriesShelf;
