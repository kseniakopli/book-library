// Страница цикла (задача 89): слева экслибрис и описание, справа — дерево книг
// со статусами (каждая книга ведёт на свою страницу), кнопки смены статуса цикла.
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { centeredSvgDataUri } from "../lib/svg";
import SeriesBookSearch from "../components/SeriesBookSearch";
import "../styles/series.css";

const STATUSES = [
  { id: "reading", label: "Читаю" },
  { id: "read", label: "Прочитан" },
  { id: "dropped", label: "Перестала читать" },
];

const BOOK_STATUS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

function SeriesPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", author: "", description: "" });

  const { data: series, isLoading } = useQuery({
    queryKey: keys.seriesOne(id),
    queryFn: () => api.getSeriesOne(id),
  });

  const refresh = (fresh) => {
    queryClient.setQueryData(keys.seriesOne(id), fresh);
    queryClient.invalidateQueries({ queryKey: keys.series });
  };

  const setStatus = useMutation({
    mutationFn: (status) => api.updateSeries({ id, status }),
    onSuccess: refresh,
  });

  const save = useMutation({
    mutationFn: () => api.updateSeries({ id, ...form }),
    onSuccess: (fresh) => {
      refresh(fresh);
      setEditing(false);
    },
  });

  // экслибрис рисуется по названию и описанию цикла — тратит токены, по кнопке
  const makeDesign = useMutation({
    mutationFn: () => api.generateSeriesDesign(id),
    onSuccess: refresh,
  });

  // picked приходит из SeriesBookSearch: либо {book_id}, либо {title, author,
  // cover_url, external_id} — второй случай заводит книгу в каталоге
  const addBook = useMutation({
    mutationFn: (picked) => api.addBookToSeries({ id, ...picked }),
    onSuccess: (fresh) => {
      refresh(fresh);
      setAdding(false);
    },
  });

  const removeBook = useMutation({
    mutationFn: (bookId) => api.removeBookFromSeries({ id, bookId }),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteSeries(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.series });
      navigate("/");
    },
  });

  // символ приходит SVG-строкой в паспорте цикла — рендерим как у книг
  const symbolUri = useMemo(
    () =>
      series?.design?.symbol_svg
        ? centeredSvgDataUri(series.design.symbol_svg)
        : null,
    [series?.design?.symbol_svg],
  );

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (!series) return <p className="error">Цикл не найден</p>;

  const { progress } = series;

  return (
    <div className="series-page">
      <div className="series-controls">
        <Link className="btn-ghost" to="/">
          ← К библиотеке
        </Link>
        <button
          className="btn-danger"
          onClick={() => {
            if (window.confirm("Удалить цикл? Книги останутся в библиотеке.")) {
              remove.mutate();
            }
          }}
        >
          Удалить цикл
        </button>
      </div>

      {/* шапка над колонками: название, автор, прогресс, статусы */}
      <header className="series-header">
        <div className="series-header-text">
          {editing ? (
            <input
              className="series-title-input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Название цикла"
            />
          ) : (
            <h1 className="series-title">{series.name}</h1>
          )}
          {!editing && series.author && (
            <p className="series-author">{series.author}</p>
          )}
          <p className="series-progress">
            Прочитано {progress.read} из {progress.total}
            {progress.on_shelf < progress.total && (
              <> · на полке {progress.on_shelf}</>
            )}
          </p>
        </div>
        <div className="series-status-row" role="group" aria-label="Статус цикла">
          {STATUSES.map((s) => (
            <button
              key={s.id}
              className={"pill " + (series.status === s.id ? "pill-active" : "")}
              onClick={() => setStatus.mutate(s.id)}
              disabled={setStatus.isPending}
              aria-pressed={series.status === s.id}
            >
              {s.label}
            </button>
          ))}
        </div>
      </header>

      <div className="series-layout">
        {/* левая колонка: экслибрис, описание, редактирование */}
        <aside className="series-aside">
          <div className="series-symbol-large" aria-hidden="true">
            {symbolUri ? (
              <img src={symbolUri} alt="" />
            ) : (
              <span className="series-symbol-empty">◆</span>
            )}
          </div>

          <button
            className="btn-ghost series-design-btn"
            onClick={() => makeDesign.mutate()}
            disabled={makeDesign.isPending}
            title={
              series.description
                ? undefined
                : "Сначала добавьте описание цикла — символ рисуется по нему"
            }
          >
            {makeDesign.isPending
              ? "Рисую символ…"
              : series.design
                ? "Обновить экслибрис"
                : "Сгенерировать экслибрис"}
          </button>
          {makeDesign.isError && (
            <p className="error">Не вышло: {makeDesign.error.message}</p>
          )}
          {series.design?.statement && (
            <p className="series-statement">{series.design.statement}</p>
          )}

          {editing ? (
            <form
              className="series-edit"
              onSubmit={(e) => {
                e.preventDefault();
                if (form.name.trim()) save.mutate();
              }}
            >
              <input
                value={form.author}
                onChange={(e) => setForm({ ...form, author: e.target.value })}
                placeholder="Автор"
              />
              <textarea
                rows={6}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="О чём цикл: мир, эпоха, что объединяет книги. По этому описанию рисуется экслибрис."
              />
              <div className="series-edit-actions">
                <button className="add-btn" type="submit" disabled={save.isPending}>
                  {save.isPending ? "Сохраняю…" : "Сохранить"}
                </button>
                <button
                  className="btn-ghost"
                  type="button"
                  onClick={() => setEditing(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          ) : (
            <>
              {series.description ? (
                <p className="series-description">{series.description}</p>
              ) : (
                <p className="muted">
                  Описания пока нет. Оно нужно, чтобы экслибрис получился
                  осмысленным.
                </p>
              )}
              <button
                className="btn-ghost series-edit-btn"
                onClick={() => {
                  setForm({
                    name: series.name,
                    author: series.author ?? "",
                    description: series.description ?? "",
                  });
                  setEditing(true);
                }}
              >
                Редактировать
              </button>
            </>
          )}
        </aside>

        {/* правая колонка: дерево книг цикла */}
        <section className="series-books">
          <div className="series-books-head">
            <h2>Книги цикла</h2>
            <button className="btn-ghost" onClick={() => setAdding((v) => !v)}>
              {adding ? "Отмена" : "+ Добавить книгу"}
            </button>
          </div>

          {adding && (
            <SeriesBookSearch
              busy={addBook.isPending}
              onPick={(picked) => addBook.mutate(picked)}
            />
          )}

          {series.books.length === 0 && !adding && (
            <p className="muted">
              В цикле пока нет книг. Добавьте их по порядку — увидите, где
              остановились.
            </p>
          )}

          <ol className="series-tree">
            {series.books.map((book) => (
              <li
                key={book.id}
                className={
                  "series-tree-item" + (book.on_shelf ? "" : " series-tree-absent")
                }
              >
                <span className="series-tree-index">
                  {book.series_index ?? "—"}
                </span>
                <span className="series-tree-body">
                  {book.on_shelf ? (
                    <Link className="series-tree-title" to={`/books/${book.id}`}>
                      {book.title}
                    </Link>
                  ) : (
                    <span className="series-tree-title">{book.title}</span>
                  )}
                  <span className="series-tree-author">{book.author}</span>
                </span>
                <span className="series-tree-status">
                  {book.on_shelf
                    ? (BOOK_STATUS[book.status] ?? book.status)
                    : "Нет в библиотеке"}
                </span>
                <button
                  className="series-tree-remove"
                  onClick={() => removeBook.mutate(book.id)}
                  title="Убрать из цикла"
                  aria-label={`Убрать «${book.title}» из цикла`}
                >
                  ×
                </button>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

export default SeriesPage;
