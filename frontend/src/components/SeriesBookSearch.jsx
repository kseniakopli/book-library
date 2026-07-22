// Поиск книги для добавления в цикл (задача 89).
// Тот же путь, что при добавлении на полку: сначала локальный каталог, потом
// Google Books, и только при пустой выдаче — «создать вручную».
// Отличие от SearchModal: выбранная книга НЕ попадает на полку, а привязывается
// к циклу; если её нет в каталоге — заводится там (без UserBook).
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";

const MIN_CHARS = 3;
const DEBOUNCE_MS = 350;

const SOURCE_LABEL = {
  library: "в библиотеке",
  catalog: "в каталоге",
  google: "Google Books",
};

function SeriesBookSearch({ onPick, busy }) {
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [index, setIndex] = useState("");
  const [manual, setManual] = useState(false);
  const [manualAuthor, setManualAuthor] = useState("");

  // дебаунс: не дёргаем поиск на каждую букву (бережём Google API)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [term]);

  const { data, isFetching } = useQuery({
    queryKey: keys.search(debounced),
    queryFn: () => api.searchBooks(debounced),
    enabled: debounced.length >= MIN_CHARS,
  });
  const results = data?.results ?? [];
  const nothingFound =
    debounced.length >= MIN_CHARS && !isFetching && results.length === 0;

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
