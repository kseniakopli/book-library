// Поиск книги для добавления в цикл (задача 89).
// Тот же путь, что при добавлении на полку: сначала локальный каталог, потом
// Google Books, и только при пустой выдаче — «создать вручную».
// Отличие от SearchModal: выбранная книга НЕ попадает на полку, а привязывается
// к циклу; если её нет в каталоге — заводится там (без UserBook).
import { useState } from "react";
import { useBookSearch } from "../hooks/useBookSearch";

const SOURCE_LABEL = {
  library: "в библиотеке",
  catalog: "в каталоге",
  google: "Google Books",
};

function SeriesBookSearch({ onPick, busy }) {
  const [term, setTerm] = useState("");
  const [index, setIndex] = useState("");
  const [manual, setManual] = useState(false);
  const [manualAuthor, setManualAuthor] = useState("");

  // поиск (debounce + запрос) — общий хук useBookSearch (R1)
  const { results, searching: isFetching, nothingFound } = useBookSearch(term);

  const numberField = (
    <input
      className="series-index-input"
      type="number"
      min="1"
      placeholder="№"
      value={index}
      onChange={(e) => setIndex(e.target.value)}
      aria-label="Номер книги в цикле"
    />
  );

  const pick = (item) =>
    onPick({
      book_id: item.book_id ?? undefined,
      title: item.book_id ? undefined : item.title,
      author: item.book_id ? undefined : item.author,
      cover_url: item.book_id ? undefined : item.cover_url,
      external_id: item.book_id ? undefined : item.external_id,
      series_index: index ? Number(index) : null,
    });

  return (
    <div className="series-search">
      <div className="series-search-row">
        <input
          autoFocus
          placeholder="Название или автор…"
          value={term}
          onChange={(e) => {
            setTerm(e.target.value);
            setManual(false);
          }}
        />
        {numberField}
      </div>

      {isFetching && <p className="muted">Ищу…</p>}

      {results.length > 0 && (
        <ul className="series-search-results">
          {results.map((item, i) => (
            <li key={`${item.title}-${i}`}>
              <button
                className="series-search-item"
                onClick={() => pick(item)}
                disabled={busy}
              >
                <span className="series-search-cover">
                  {item.cover_url ? (
                    <img src={item.cover_url} alt="" loading="lazy" />
                  ) : (
                    <span className="series-search-cover-empty">—</span>
                  )}
                </span>
                <span className="series-search-text">
                  <span className="series-search-title">{item.title}</span>
                  <span className="series-search-author">{item.author}</span>
                </span>
                <span className="series-search-source">
                  {SOURCE_LABEL[item.source] ?? item.source}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* пустая выдача — как при добавлении книги: заводим вручную */}
      {nothingFound && !manual && (
        <p className="muted">
          Ничего не нашлось.{" "}
          <button className="btn-ghost" onClick={() => setManual(true)}>
            Добавить вручную
          </button>
        </p>
      )}

      {manual && (
        <form
          className="series-search-manual"
          onSubmit={(e) => {
            e.preventDefault();
            if (term.trim()) {
              onPick({
                title: term.trim(),
                author: manualAuthor.trim(),
                series_index: index ? Number(index) : null,
              });
            }
          }}
        >
          <input
            placeholder="Автор"
            value={manualAuthor}
            onChange={(e) => setManualAuthor(e.target.value)}
          />
          <button className="add-btn" type="submit" disabled={busy}>
            {busy ? "Добавляю…" : `Добавить «${term.trim()}»`}
          </button>
        </form>
      )}

      <p className="muted series-add-hint">
        Книги, которых у вас ещё нет, тоже можно добавить — они покажут, что
        читать дальше. На полку они не попадут.
      </p>
    </div>
  );
}

export default SeriesBookSearch;
