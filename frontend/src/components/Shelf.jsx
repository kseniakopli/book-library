import { useEffect, useRef, useState } from "react";
import BookCard from "./BookCard";

// Раскладка полки по ширине экрана: сколько карточек в ряду (десктоп — стрелки)
// и мобильный ли режим (тогда — свайп scroll-snap вместо стрелок, задача 51)
function useShelfLayout() {
  const compute = () => {
    const w = window.innerWidth;
    if (w < 560) return { pageSize: 2, isMobile: true };
    if (w < 900) return { pageSize: 3, isMobile: false };
    return { pageSize: 5, isMobile: false };
  };
  const [layout, setLayout] = useState(compute);
  useEffect(() => {
    const onResize = () => setLayout(compute());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return layout;
}

// Полка управляемая: позиция листания (start) хранится у родителя (HomePage),
// поэтому не сбрасывается при возврате из карточки книги.
// Задача 70 (ленивая загрузка): books — только ЗАГРУЖЕННЫЕ книги, total — сколько
// всего на полке; когда листание упирается в край загруженного, зовём onLoadMore.
function Shelf({
  title,
  books = [],
  total = books.length,
  hasMore = false,
  onLoadMore,
  onSelect,
  placeholder,
  start = 0,
  onStart,
  symbolMode = false,
  designs = {},
  theme = "light",
}) {
  const { pageSize, isMobile } = useShelfLayout();

  // все вычисления и эффекты — ДО ранних return (правила хуков)
  const maxStart = Math.max(0, total - pageSize);
  const safeStart = Math.min(start, maxStart);   // на случай смены pageSize при ресайзе

  // Мобильный свайп: невидимый «хвост» в конце ленты; доехал до него —
  // догружаем следующую страницу (IntersectionObserver, root = сама лента)
  const swipeRef = useRef(null);
  const moreRef = useRef(null);
  useEffect(() => {
    if (!isMobile || !hasMore || !moreRef.current || !onLoadMore) return;
    const observer = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && onLoadMore(),
      { root: swipeRef.current, rootMargin: "200px" },
    );
    observer.observe(moreRef.current);
    return () => observer.disconnect();
  }, [isMobile, hasMore, onLoadMore, books.length]);

  // Десктоп: сохранённая позиция листания (sessionStorage) после F5 может
  // указывать за край загруженного — догружаем страницы, пока не доедем
  useEffect(() => {
    if (isMobile || !hasMore || !onLoadMore) return;
    if (safeStart + pageSize > books.length) onLoadMore();
  }, [isMobile, hasMore, onLoadMore, safeStart, pageSize, books.length]);

  if (placeholder) {
    return (
      <section className="shelf">
        <div className="shelf-head">
          <h2 className="shelf-title">{title}</h2>
        </div>
        <p className="shelf-placeholder">{placeholder}</p>
      </section>
    );
  }

  if (books.length === 0) {
    return (
      <section className="shelf">
        <div className="shelf-head">
          <h2 className="shelf-title">{title}</h2>
        </div>
        <p className="shelf-empty">Здесь пока пусто</p>
      </section>
    );
  }

  // Задача 51: на телефоне — свайп (нативная горизонтальная прокрутка со
  // scroll-snap) вместо стрелок; книги догружаются по мере прокрутки (задача 70).
  if (isMobile) {
    return (
      <section className="shelf">
        <div className="shelf-head">
          <h2 className="shelf-title">
            {title} <span className="shelf-count">{total}</span>
          </h2>
        </div>
        <div className="shelf-swipe" ref={swipeRef}>
          {books.map((book) => (
            <div className="shelf-swipe-item" key={book.id}>
              <BookCard
                book={book}
                onSelect={onSelect}
                symbolMode={symbolMode}
                design={designs[book.id]}
                theme={theme}
              />
            </div>
          ))}
          {hasMore && (
            <div className="shelf-swipe-more" ref={moreRef} aria-hidden="true" />
          )}
        </div>
      </section>
    );
  }

  const canPrev = safeStart > 0;
  const canNext = safeStart + pageSize < total;
  const visible = books.slice(safeStart, safeStart + pageSize);

  const move = (delta) => {
    const next = Math.min(Math.max(safeStart + delta, 0), maxStart);
    // упёрлись в край загруженного, а на полке есть ещё — догружаем страницу;
    // React Query дозаполнит кэш, и slice ниже дорисует карточки сам
    if (next + pageSize > books.length && hasMore && onLoadMore) onLoadMore();
    if (onStart) onStart(next);
  };

  return (
    <section className="shelf">
      <div className="shelf-head">
        <h2 className="shelf-title">
          {title} <span className="shelf-count">{total}</span>
        </h2>
        {total > pageSize && (
          <span className="shelf-range">
            {safeStart + 1}–{Math.min(safeStart + pageSize, total)} из {total}
          </span>
        )}
      </div>
      <div className="shelf-body">
        <button
          className="shelf-arrow"
          onClick={() => move(-pageSize)}
          disabled={!canPrev}
          aria-label="Назад"
        >
          ‹
        </button>
        <div
          className="shelf-row"
          style={{ gridTemplateColumns: `repeat(${pageSize}, minmax(0, 1fr))` }}
        >
          {visible.map((book) => (
            <BookCard
              key={book.id}
              book={book}
              onSelect={onSelect}
              symbolMode={symbolMode}
              design={designs[book.id]}
              theme={theme}
            />
          ))}
        </div>
        <button
          className="shelf-arrow"
          onClick={() => move(pageSize)}
          disabled={!canNext}
          aria-label="Вперёд"
        >
          ›
        </button>
      </div>
    </section>
  );
}

export default Shelf;
