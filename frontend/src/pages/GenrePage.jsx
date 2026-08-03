// Книги одного жанра (задача 112).
//
// Две стопки, как на странице автора: «на полке» — то, что читатель завёл
// у себя, «есть в каталоге» — остальные книги жанра из общей базы. Вторая
// стопка здесь не бонус, а половина смысла: по ней и выбирают, что читать.
//
// Плитка книги и стили общие со страницей автора (ревью 03.08): до этого
// `BookTile` был скопирован сюда целиком.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import BookTile from "../components/BookTile";
import { shelfNote } from "../lib/bookLabels";
import "../styles/catalog.css";

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
    <div className="catalog-page">
      <Link className="btn-ghost" to="/genres">
        ← Ко всем жанрам
      </Link>

      <header className="catalog-head">
        <h1 className="catalog-name">{data.name}</h1>
        <p className="muted">
          {shelf.length > 0
            ? `На полке: ${shelf.length}`
            : "На полке пока ничего нет"}
          {catalog.length > 0 ? ` · в каталоге ещё ${catalog.length}` : ""}
        </p>
      </header>

      {shelf.length > 0 && (
        <section className="catalog-section">
          <h2 className="catalog-section-title">На полке</h2>
          <ul className="catalog-books">
            {shelf.map((book) => (
              <BookTile key={book.id} book={book} note={shelfNote(book)} />
            ))}
          </ul>
        </section>
      )}

      {catalog.length > 0 && (
        <section className="catalog-section">
          <h2 className="catalog-section-title">Есть в каталоге</h2>
          <p className="muted catalog-section-lead">
            Книги этого жанра, которых нет у вас на полке.
          </p>
          <ul className="catalog-books">
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
