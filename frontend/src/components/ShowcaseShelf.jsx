// Полка витрины (28.07): книги одной горизонтальной лентой вместо сетки.
//
// Почему не переиспользуем Shelf с главной: та полка завязана на BookCard,
// постраничную догрузку и сохранение позиции листания — всё это про личную
// библиотеку. Витрина публичная, книг там десяток и они приходят разом,
// поэтому здесь достаточно нативной прокрутки со scroll-snap.
//
// Стрелки — те же `.shelf-arrow` (styles/shelf.css подключён глобально):
// на витрине незачем заводить второй вид одной и той же кнопки.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { centeredSvgDataUri } from "../lib/svg";
import { pickPalette, pickPaletteForSymbol } from "../lib/palette";

function ShowcaseCard({ slug, book, theme }) {
  const design = book.design;
  const symbol = design?.symbol_svg ? centeredSvgDataUri(design.symbol_svg) : null;
  // Плашка с символом красится палитрой, на которой символ ВИДЕН (28.07),
  // а карточка без символа — палитрой по теме, как всё остальное.
  const palette = symbol ? pickPaletteForSymbol(design) : pickPalette(design, theme);

  return (
    <li className="showcase-item">
      <Link className="showcase-card" to={`/u/${slug}/books/${book.id}`}>
        <span
          className={"showcase-cover" + (symbol ? " showcase-cover-symbol" : "")}
          style={palette ? { background: palette.bg } : undefined}
        >
          {symbol ? (
            <img src={symbol} alt="" aria-hidden="true" />
          ) : book.cover_url ? (
            <img src={book.cover_url} alt="" loading="lazy" />
          ) : null}
        </span>
        <span className="showcase-title">{book.title}</span>
        <span className="showcase-author">{book.author}</span>
      </Link>
    </li>
  );
}

function ShowcaseShelf({ books, slug, theme }) {
  const stripRef = useRef(null);
  // состояние краёв: у левого — прячем «назад», у правого — «вперёд»
  const [edges, setEdges] = useState({ start: true, end: true });

  const sync = useCallback(() => {
    const strip = stripRef.current;
    if (!strip) return;
    const max = strip.scrollWidth - strip.clientWidth;
    setEdges({
      start: strip.scrollLeft <= 1,
      // всё поместилось (max ≈ 0) — считаем, что мы и в начале, и в конце:
      // тогда обе стрелки не нужны вовсе
      end: strip.scrollLeft >= max - 1,
    });
  }, []);

  useEffect(() => {
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, [sync, books.length]);

  // листаем почти на экран, оставляя карточку внахлёст — так видно, что лента
  // продолжается, и глаз не теряет место
  const move = (direction) => {
    const strip = stripRef.current;
    if (!strip) return;
    strip.scrollBy({ left: direction * strip.clientWidth * 0.85, behavior: "smooth" });
  };

  const fits = edges.start && edges.end; // прокручивать нечего

  return (
    <div className="showcase-shelf">
      {!fits && (
        <button
          className="shelf-arrow showcase-arrow showcase-arrow-prev"
          onClick={() => move(-1)}
          disabled={edges.start}
          aria-label="Предыдущие книги"
        >
          ‹
        </button>
      )}
      <ul className="showcase-strip" ref={stripRef} onScroll={sync}>
        {books.map((book) => (
          <ShowcaseCard key={book.id} slug={slug} book={book} theme={theme} />
        ))}
      </ul>
      {!fits && (
        <button
          className="shelf-arrow showcase-arrow showcase-arrow-next"
          onClick={() => move(1)}
          disabled={edges.end}
          aria-label="Следующие книги"
        >
          ›
        </button>
      )}
    </div>
  );
}

export default ShowcaseShelf;
