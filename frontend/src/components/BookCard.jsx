import { useMemo } from "react";
import { STATUS_LABELS } from "../constants";
import { useImageFallback } from "../hooks/useImageFallback";
import { centeredSvgDataUri } from "../lib/svg";
import { pickPalette } from "../lib/palette";

// symbolMode + design + theme (задача 66): в символьном режиме карточка рисует
// экслибрис на палитре паспорта вместо обложки. Нет паспорта — обычный вид.
function BookCard({
  book,
  onSelect,
  symbolMode = false,
  design = null,
  theme = "light",
}) {
  // палитра по теме интерфейса (единое правило — lib/palette)
  const palette = pickPalette(design, theme);

  const symbolUri = useMemo(
    () => (design?.symbol_svg ? centeredSvgDataUri(design.symbol_svg) : null),
    [design?.symbol_svg],
  );
  // символ мог сгенерироваться битым, обложка — пропасть по ссылке;
  // в обоих случаях откатываемся на заглушку (хук useImageFallback)
  const symbol = useImageFallback();
  const cover = useImageFallback();
  const showSymbol = symbolMode && palette && symbol.ok(symbolUri);

  // логотип-полумесяц: и для книг без паспорта, и как фолбэк для битого символа
  const moon = (
    <div className="cover-moon" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <mask id={`moon-${book.id}`}>
          <rect width="24" height="24" fill="#000" />
          <circle cx="11" cy="12" r="9" fill="#fff" />
          <circle cx="16" cy="12" r="8" fill="#000" />
        </mask>
        <rect
          width="24"
          height="24"
          fill="currentColor"
          mask={`url(#moon-${book.id})`}
        />
      </svg>
    </div>
  );

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
      <div
        className="cover"
        style={showSymbol ? { background: palette.bg } : undefined}
      >
        {symbolMode ? (
          showSymbol ? (
            // паспорт есть — экслибрис на палитре
            <div className="cover-symbol">
              <img src={symbolUri} alt="" aria-hidden="true" onError={symbol.onError} />
            </div>
          ) : (
            // нет паспорта или битый символ — логотип-полумесяц (полка единая)
            moon
          )
        ) : cover.ok(book.cover_url) ? (
          // задача 56: lazy — браузер грузит обложку при приближении к экрану
          <img src={book.cover_url} alt="" loading="lazy" onError={cover.onError} />
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
