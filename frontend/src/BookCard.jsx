const STATUS_LABELS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

function BookCard({ book, onSelect }) {
  return (
    <article className="book" onClick={() => onSelect(book)}>
      <div className="cover">
        {book.cover_url ? (
          <img src={book.cover_url} alt={book.title} />
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