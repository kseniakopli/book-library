import { useMemo, useState } from "react";
import { STATUS_LABELS } from "../constants";
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
  // символ мог сгенерироваться битым (обрезанный/невалидный SVG) — тогда
  // <img> не отрисуется; ловим onError и откатываемся на полумесяц
  const [symbolBroken, setSymbolBroken] = useState(false);
  // обложка может не загрузиться (битая/пропавшая ссылка) — тогда честная заглушка
  const [coverBroken, setCoverBroken] = useState(false);
  const showSymbol = symbolMode && palette && symbolUri && !symbolBroken;

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
              <img
                src={symbolUri}
                alt=""
                aria-hidden="true"
                onError={() => setSymbolBroken(true)}
              />
            </div>
          ) : (
            // нет паспорта или битый символ — логотип-полумесяц (полка единая)
            moon
          )
        ) : book.cover_url && !coverBroken ? (
          // задача 56: lazy — браузер грузит обложку при приближении к экрану
          <img
            src={book.cover_url}
            alt=""
            loading="lazy"
            onError={() => setCoverBroken(true)}
          />
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
