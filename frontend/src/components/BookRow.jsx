// Строка книги в списке справочной страницы — автора (з.97) и цикла (з.89).
// Появилась в задаче 119, когда обе страницы свели к одному макету.
//
// ⚠ Это НЕ `BookTile`: та показывает книгу плиткой с обложкой и живёт
// на странице жанра, которая осталась одноколоночной. И не `BookCard`
// с полки — там палитра паспорта, символьный режим и оценка.
// Здесь книга — строка справочника: порядок, название, подпись, пометка.
//
// Все части необязательны, и это осознанно: у автора нет ни номера тома,
// ни крестика «убрать», у цикла нет подписи с автором в списке одного
// человека. Компонент один, а строки получаются разные.
import { Link } from "react-router-dom";

function BookRow({ book, index, subtitle, note, year, muted = false, onRemove }) {
  return (
    <li className={"entity-row" + (muted ? " entity-row-muted" : "")}>
      {index !== undefined && (
        <span className="entity-row-index">{index ?? "—"}</span>
      )}

      <span className="entity-row-body">
        <span className="entity-row-line">
          <Link className="entity-row-title" to={`/books/${book.id}`}>
            {book.title}
          </Link>
          {/* Задача 121: год рядом с названием, но ВНЕ ссылки — кликать
              по нему незачем, а внутри он удлинял бы цель нажатия
              и читался бы как часть заголовка книги. */}
          {year != null && <span className="entity-row-year">{year}</span>}
        </span>
        {subtitle && <span className="entity-row-sub">{subtitle}</span>}
      </span>

      {note && <span className="entity-row-note">{note}</span>}

      {onRemove && (
        <button
          className="entity-row-remove"
          onClick={() => onRemove(book.id)}
          title="Убрать из цикла"
          aria-label={`Убрать «${book.title}» из цикла`}
        >
          ×
        </button>
      )}
    </li>
  );
}

export default BookRow;
