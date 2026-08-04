// Правая колонка страницы цикла: список книг + добавление новой.
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
//
// ⚠ Задача 119: строка книги переехала в общий `BookRow` — тот же компонент
// рисует списки на странице автора. Своя разметка `series-tree-*` была
// первой из двух, и вторая приехала бы копипастом.
import BookRow from "./BookRow";
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
    <section>
      <div className="entity-section-head">
        <h2 className="entity-section-title">Книги цикла</h2>
        <button className="btn-ghost" onClick={onToggleAdding}>
          {adding ? "Отмена" : "+ Добавить книгу"}
        </button>
      </div>

      {adding && <SeriesBookSearch busy={addPending} onPick={onPick} />}

      {books.length === 0 && !adding && (
        <p className="muted entity-empty">
          В цикле пока нет книг. Добавьте их по порядку — увидите, где
          остановились.
        </p>
      )}

      <ol className="entity-rows">
        {books.map((book) => (
          <BookRow
            key={book.id}
            book={book}
            // null, а не undefined: у тома без номера должно остаться «—»,
            // иначе строка съедет влево и колонка номеров развалится
            index={book.series_index ?? null}
            subtitle={authorLabel(book)}
            note={
              book.on_shelf
                ? (BOOK_STATUS[book.status] ?? book.status)
                : "Нет на полке"
            }
            muted={!book.on_shelf}
            onRemove={onRemove}
          />
        ))}
      </ol>
    </section>
  );
}

export default SeriesBookTree;
