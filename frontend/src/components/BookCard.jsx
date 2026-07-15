import { STATUS_LABELS } from "../constants";

function BookCard({ book, onSelect }) {
  // Карточка кликабельна и с клавиатуры (задача 23): Enter или пробел
  function onKeyDown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(book);
    }
  }

  return (
    <article
      className="book"
      role="button"
      tabIndex={0}
      onClick={() => onSelect(book)}
      onKeyDown={onKeyDown}
      aria-label={`${book.title} — ${book.author}`}
    >
      <div className="cover">
        {book.cover_url ? (
          <img src={book.cover_url} alt="" />
        ) : (
          <div className="cover-empty">Нет обложки</div>
        )}
      </div>
      <h3 className="book-title">{book.title}</h3>
      <p className="book-author">{book.author}</p>
      <div className="book-meta">
        <span className="status">{STATUS_LABELS[book.status]}</span>
        {book.status === "read" && book.rating != null && (
          <span className="rating">★ {book.rating}/10</span>
        )}
      </div>
    </article>
  );
}

export default BookCard;
