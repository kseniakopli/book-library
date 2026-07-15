import { useEffect, useState } from "react";
import BookCard from "./BookCard";

// Сколько карточек в ряду — зависит от ширины экрана (адаптивность)
function usePageSize() {
  const compute = () => {
    const w = window.innerWidth;
    if (w < 560) return 2;
    if (w < 900) return 3;
    return 5;
  };
  const [size, setSize] = useState(compute);
  useEffect(() => {
    const onResize = () => setSize(compute());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return size;
}

// Полка управляемая: позиция листания (start) хранится у родителя (App),
// поэтому не сбрасывается при возврате из карточки книги.
function Shelf({ title, books = [], onSelect, placeholder, start = 0, onStart }) {
  const pageSize = usePageSize();

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

  const maxStart = Math.max(0, books.length - pageSize);
  const safeStart = Math.min(start, maxStart);   // на случай смены pageSize при ресайзе
  const canPrev = safeStart > 0;
  const canNext = safeStart + pageSize < books.length;
  const visible = books.slice(safeStart, safeStart + pageSize);

  const move = (delta) => {
    const next = Math.min(Math.max(safeStart + delta, 0), maxStart);
    if (onStart) onStart(next);
  };

  return (
    <section className="shelf">
      <h2 className="shelf-title">{title} <span className="shelf-count">{books.length}</span></h2>
      <div className="shelf-body">
        <button className="shelf-arrow" onClick={() => move(-pageSize)} disabled={!canPrev} aria-label="Назад">‹</button>
        <div
          className="shelf-row"
          style={{ gridTemplateColumns: `repeat(${pageSize}, minmax(0, 1fr))` }}
        >
          {visible.map((book) => (
            <BookCard key={book.id} book={book} onSelect={onSelect} />
          ))}
        </div>
        <button className="shelf-arrow" onClick={() => move(pageSize)} disabled={!canNext} aria-label="Вперёд">›</button>
      </div>
    </section>
  );
}

export default Shelf;
