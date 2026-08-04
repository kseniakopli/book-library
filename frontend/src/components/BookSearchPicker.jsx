// Поиск книги для привязки к сущности — общий для цикла (з.89) и автора (з.123).
//
// Путь один и тот же: локальный каталог → Google Books → «добавить вручную»
// при пустой выдаче. Отличается только то, что делают с найденным, поэтому
// компонент отвечает за «показать и выбрать», а вызывающий — за «куда деть».
//
// ⚠ Вынесено при задаче 123. До неё это была разметка `SeriesBookSearch`,
// и второй экран скопировал бы её целиком — ровно тот случай, который
// в `Уроки.md` записан как «правка, скопированная в два места»: заглушку
// обложки или порог поиска потом чинили бы в одном файле из двух.
//
// Отличия между случаями вынесены в пропсы, а не в флаги «режимов»:
//   `extraField` — номер тома у цикла, у автора его нет;
//   `allowLocal` — можно ли выбирать книгу, которая уже есть в базе;
//   `askAuthor`  — спрашивать ли автора при ручном вводе: у цикла книга
//                  может быть чьей угодно, у автора строка берётся со
//                  страницы (з.123, иначе привязка уедет к другому автору);
//   `hint`       — подпись под формой, у каждого экрана своя.
import { useState } from "react";
import { useBookSearch } from "../hooks/useBookSearch";
import "../styles/search.css";

const SOURCE_LABEL = {
  library: "в библиотеке",
  catalog: "в каталоге",
  google: "Google Books",
};

function BookSearchPicker({
  onPick,
  busy,
  extraField = null,
  allowLocal = true,
  askAuthor = true,
  hint,
  localNote = "уже в базе",
}) {
  const [term, setTerm] = useState("");
  const [manual, setManual] = useState(false);
  const [manualAuthor, setManualAuthor] = useState("");

  const { results, searching, nothingFound } = useBookSearch(term);

  return (
    <div className="book-search">
      <div className="book-search-row">
        <input
          autoFocus
          placeholder="Название или автор…"
          value={term}
          onChange={(e) => {
            setTerm(e.target.value);
            setManual(false);
          }}
          aria-label="Поиск книги"
        />
        {extraField}
      </div>

      {searching && <p className="muted">Ищу…</p>}

      {results.length > 0 && (
        <ul className="book-search-results">
          {results.map((item, i) => {
            // книга уже в базе: где-то её можно привязать (цикл), а где-то
            // нет (автор — она уже привязана к своему, см. з.123)
            const isLocal = Boolean(item.book_id);
            const blocked = isLocal && !allowLocal;
            return (
              <li key={`${item.title}-${i}`}>
                <button
                  className="book-search-item"
                  onClick={() => onPick(item)}
                  disabled={busy || blocked}
                  title={blocked ? localNote : undefined}
                >
                  <span className="book-search-cover">
                    {item.cover_url ? (
                      <img src={item.cover_url} alt="" loading="lazy" />
                    ) : (
                      <span className="book-search-cover-empty">—</span>
                    )}
                  </span>
                  <span className="book-search-text">
                    <span className="book-search-title">{item.title}</span>
                    <span className="book-search-author">{item.author}</span>
                  </span>
                  <span className="book-search-source">
                    {blocked ? localNote : (SOURCE_LABEL[item.source] ?? item.source)}
                  </span>
                </button>
              </li>
            );
          })}
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
          className="book-search-manual"
          onSubmit={(e) => {
            e.preventDefault();
            if (term.trim()) {
              onPick({
                title: term.trim(),
                author: manualAuthor.trim(),
                manual: true,
              });
            }
          }}
        >
          {askAuthor && (
            <input
              placeholder="Автор"
              value={manualAuthor}
              onChange={(e) => setManualAuthor(e.target.value)}
              aria-label="Автор книги"
            />
          )}
          <button className="add-btn" type="submit" disabled={busy}>
            {busy ? "Добавляю…" : `Добавить «${term.trim()}»`}
          </button>
        </form>
      )}

      {hint && <p className="muted book-search-hint">{hint}</p>}
    </div>
  );
}

export default BookSearchPicker;
