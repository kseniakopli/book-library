// Книги одного жанра (задача 112).
//
// Две стопки, как на странице автора: «на полке» — то, что читатель завёл
// у себя, «есть в каталоге» — остальные книги жанра из общей базы. Вторая
// стопка здесь не бонус, а половина смысла: по ней и выбирают, что читать.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useImageFallback } from "../hooks/useImageFallback";
import "../styles/author.css";

const STATUS_LABEL = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

function BookTile({ book, note }) {
  const cover = useImageFallback();

  return (
    <li className="author-book">
      <Link className="author-book-link" to={`/books/${book.id}`}>
        <span className="author-book-cover">
          {book.cover_url && cover.ok(book.cover_url) ? (
            <img src={book.cover_url} alt="" loading="lazy" onError={cover.onError} />
          ) : (
            <span className="author-book-empty">Нет обложки</span>
          )}
        </span>
        <span className="author-book-title">{book.title}</span>
        {note && <span className="author-book-note">{note}</span>}
      </Link>
    </li>
  );
}

function GenrePage() {
  const { id } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.genre(id),
    queryFn: () => api.getGenre(id),
    retry: false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Жанр не найден.</p>;

  const { shelf = [], catalog = [] } = data;

  return (
    <div className="author-page">
      <Link className="btn-ghost" to="/genres">
        ← Ко всем жанрам
      </Link>

      <header className="author-head">
        <h1 className="author-name">{data.name}</h1>
        <p className="muted">
          {shelf.length > 0
            ? `На полке: ${shelf.length}`
            : "На полке пока ничего нет"}
          {catalog.length > 0 ? ` · в каталоге ещё ${catalog.length}` : ""}
        </p>
      </header>

      {shelf.length > 0 && (
        <section className="author-section">
          <h2 className="author-section-title">На полке</h2>
          <ul className="author-books">
            {shelf.map((book) => (
              <BookTile
                key={book.id}
                book={book}
                note={
                  book.rating
                    ? `${STATUS_LABEL[book.status]} · ★ ${book.rating}/10`
                    : STATUS_LABEL[book.status]
                }
              />
            ))}
          </ul>
        </section>
      )}

      {catalog.length > 0 && (
        <section className="author-section">
          <h2 className="author-section-title">Есть в каталоге</h2>
          <p className="muted author-section-lead">
            Книги этого жанра, которых нет у вас на полке.
          </p>
          <ul className="author-books">
            {catalog.map((book) => (
              <BookTile key={book.id} book={book} note={book.author} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default GenrePage;
