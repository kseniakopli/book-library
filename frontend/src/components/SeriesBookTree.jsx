// Правая колонка страницы цикла: дерево книг + добавление новой.
// Вынесено из SeriesPage (R4, 26.07).
//
// Книги цикла бывают двух видов: те, что на полке читателя (ведут на свою
// страницу), и «что дальше» — записи каталога без UserBook. Второй вид
// показывается приглушённо и с пометкой «Нет в библиотеке» (задача 89).
import { Link } from "react-router-dom";
import SeriesBookSearch from "./SeriesBookSearch";

const BOOK_STATUS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

function SeriesBookTree({
  books,
  adding,
  onToggleAdding,
  onPick,
  addPending,
  onRemove,
}) {
  return (
    <section className="series-books">
      <div className="series-books-head">
        <h2>Книги цикла</h2>
        <button className="btn-ghost" onClick={onToggleAdding}>
          {adding ? "Отмена" : "+ Добавить книгу"}
        </button>
      </div>

      {adding && <SeriesBookSearch busy={addPending} onPick={onPick} />}

      {books.length === 0 && !adding && (
        <p className="muted">
          В цикле пока нет книг. Добавьте их по порядку — увидите, где
          остановились.
        </p>
      )}

      <ol className="series-tree">
        {books.map((book) => (
          <li
            key={book.id}
            className={
              "series-tree-item" + (book.on_shelf ? "" : " series-tree-absent")
            }
          >
            <span className="series-tree-index">{book.series_index ?? "—"}</span>
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
              onClick={() => onRemove(book.id)}
              title="Убрать из цикла"
              aria-label={`Убрать «${book.title}» из цикла`}
            >
              ×
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default SeriesBookTree;
