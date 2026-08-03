// Справочник авторов (задача 111, первая часть).
//
// ⚠ Раздел про то, что есть в БАЗЕ сервиса, а не про личную полку (решение
// Ксении 03.08): числа считаются по общему каталогу, и список одинаков для
// всех. Что из этого лежит на полке лично у читателя, показывает страница
// автора — там книги разложены на две стопки.
//
// Биографии (`Author.bio`) — остаток задачи 111, отдельной правкой с миграцией.
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import "../styles/authors.css";

/** «5 книг» / «1 книга» / «2 книги» — без склонения число выглядит машинным. */
function booksLabel(n) {
  const tens = n % 100;
  const ones = n % 10;
  if (tens >= 11 && tens <= 14) return `${n} книг`;
  if (ones === 1) return `${n} книга`;
  if (ones >= 2 && ones <= 4) return `${n} книги`;
  return `${n} книг`;
}

function AuthorsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.authors,
    queryFn: api.getAuthors,
  });

  const authors = data?.authors ?? [];

  return (
    <div className="authors-page">
      <Link className="btn-ghost" to="/">
        ← К библиотеке
      </Link>

      <header className="authors-head">
        <h1 className="title">Авторы</h1>
        {authors.length > 0 && (
          <p className="muted">Всего: {authors.length}</p>
        )}
      </header>

      {isLoading && <p className="muted">Загрузка…</p>}
      {isError && <p className="error">Не удалось загрузить список авторов.</p>}

      {!isLoading && !isError && authors.length === 0 && (
        <p className="muted">
          Авторы появятся, когда в библиотеке будут книги.
        </p>
      )}

      {authors.length > 0 && (
        <ul className="authors-list">
          {authors.map((author) => (
            <li key={author.id}>
              <Link className="authors-item" to={`/authors/${author.id}`}>
                <span className="authors-name">{author.name}</span>
                <span className="authors-count">{booksLabel(author.books)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AuthorsPage;
