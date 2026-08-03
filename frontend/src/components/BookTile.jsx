// Плитка книги для справочных страниц — автора (з.97) и жанра (з.112).
//
// Вынесено из обеих страниц (ревью 03.08, пункт Ф1): жанры делались по образцу
// авторов, и плитка приехала туда копипастом вместе с разметкой и хуком.
// Правка заглушки обложки прошла бы в одном файле из двух — ровно тот случай,
// который в `Уроки.md` записан как «правка, скопированная в два места».
//
// ⚠ Это НЕ `BookCard` с полки: там статус, оценка, символьный режим и палитра
// паспорта. Здесь книга показывается как элемент справочника — обложка,
// название и одна поясняющая строка. Объединять их не стоит: общего меньше,
// чем различий, и `BookCard` тянет за собой три пропа про оформление.
// ⚠ Отсюда ничего, кроме компонента, не экспортируется: файл с двумя видами
// экспорта ломает Fast Refresh (oxlint: react/only-export-components).
// Подпись `shelfNote` живёт в `lib/bookLabels.js`.
import { Link } from "react-router-dom";
import { useImageFallback } from "../hooks/useImageFallback";

function BookTile({ book, note }) {
  const cover = useImageFallback();

  return (
    <li className="catalog-book">
      <Link className="catalog-book-link" to={`/books/${book.id}`}>
        <span className="catalog-book-cover">
          {book.cover_url && cover.ok(book.cover_url) ? (
            <img src={book.cover_url} alt="" loading="lazy" onError={cover.onError} />
          ) : (
            <span className="catalog-book-empty">Нет обложки</span>
          )}
        </span>
        <span className="catalog-book-title">{book.title}</span>
        {note && <span className="catalog-book-note">{note}</span>}
      </Link>
    </li>
  );
}

export default BookTile;
