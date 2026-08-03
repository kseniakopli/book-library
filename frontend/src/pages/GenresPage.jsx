// Справочник жанров (задача 112).
//
// ⚠ Как и авторы, считается по ОБЩЕМУ каталогу, а не по полке спрашивающего:
// раздел отвечает на вопрос «что есть в библиотеке».
//
// Жанры заводятся ВРУЧНУЮ на странице книги. Google Books отдаёт
// «Fiction / General» — это рубрикатор магазина, а не жанр, и источником
// данных он здесь не работает.
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { booksLabel } from "../lib/plural";
import "../styles/authors.css";

function GenresPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.genres,
    queryFn: api.getGenres,
  });

  const genres = data?.genres ?? [];

  return (
    <div className="authors-page">
      <Link className="btn-ghost" to="/">
        ← К библиотеке
      </Link>

      <header className="authors-head">
        <h1 className="title">Жанры</h1>
        {genres.length > 0 && <p className="muted">Всего: {genres.length}</p>}
      </header>

      {isLoading && <p className="muted">Загрузка…</p>}
      {isError && <p className="error">Не удалось загрузить список жанров.</p>}

      {!isLoading && !isError && genres.length === 0 && (
        <p className="muted">
          Жанров пока нет. Они проставляются вручную на странице книги —
          Google Books присылает рубрики вроде «Fiction / General», и жанрами
          они не считаются.
        </p>
      )}

      {genres.length > 0 && (
        <ul className="authors-list">
          {genres.map((genre) => (
            <li key={genre.id}>
              <Link className="authors-item" to={`/genres/${genre.id}`}>
                <span className="authors-name">{genre.name}</span>
                <span className="authors-count">{booksLabel(genre.books)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default GenresPage;
