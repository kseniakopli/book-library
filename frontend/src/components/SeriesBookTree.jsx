// Правая колонка страницы цикла: дерево книг + добавление новой.
// Вынесено из SeriesPage (R4, 26.07).
//
// Книги цикла бывают двух видов: те, что на полке читателя, и «что дальше» —
// записи каталога без UserBook. Второй вид показывается приглушённо
// и с пометкой «Нет на полке» (задача 89).
//
// ⚠ Правка 03.08: раньше вторые были НЕ кликабельны, и это было верно —
// страница книги отдавала 404 всем, кроме владельца полки. Ограничение сняли
// (книга — общая сущность каталога), поэтому ссылка теперь у всех: про том,
// которого у тебя нет, как раз и хочется прочитать, ради этого цикл
// и показывает продолжение.
// Заодно поправлена формулировка: «Нет в библиотеке» было неточным — книга
// в библиотеке есть, её нет на ПОЛКЕ. Эта путаница и мешала заметить,
// что ссылку можно вернуть.
import { Link } from "react-router-dom";
import { authorLabel } from "../lib/bookLabels";
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
              <Link className="series-tree-title" to={`/books/${book.id}`}>
                {book.title}
              </Link>
              <span className="series-tree-author">{authorLabel(book)}</span>
            </span>
            <span className="series-tree-status">
              {book.on_shelf
                ? (BOOK_STATUS[book.status] ?? book.status)
                : "Нет на полке"}
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
