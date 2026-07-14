import { useState } from "react";
import BookCard from "./BookCard";

const PAGE = 5;

function Shelf({ title, books = [], onSelect, placeholder }) {
  const [start, setStart] = useState(0);

  if (placeholder) {
    return (
      <section className="shelf">
        <h2 className="shelf-title">{title}</h2>
        <p className="shelf-placeholder">{placeholder}</p>
      </section>
    );
  }

  if (books.length === 0) {
    return (
      <section className="shelf">
        <h2 className="shelf-title">{title}</h2>
        <p className="shelf-empty">Здесь пока пусто</p>
      </section>
    );
  }

  const canPrev = start > 0;
  const canNext = start + PAGE < books.length;
  const visible = books.slice(start, start + PAGE);

  return (
    <section className="shelf">
      <h2 className="shelf-title">{title} <span className="shelf-count">{books.length}</span></h2>
      <div className="shelf-body">
        <button className="shelf-arrow" onClick={() => setStart(start - PAGE)} disabled={!canPrev} aria-label="Назад">‹</button>
        <div className="shelf-row">
          {visible.map((book) => (
            <BookCard key={book.id} book={book} onSelect={onSelect} />
          ))}
        </div>
        <button className="shelf-arrow" onClick={() => setStart(start + PAGE)} disabled={!canNext} aria-label="Вперёд">›</button>
      </div>
    </section>
  );
}

export default Shelf;