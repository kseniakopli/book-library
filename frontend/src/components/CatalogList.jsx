// Справочник каталога: список «имя + число книг» (ревью 03.08, пункт Ф2).
//
// Общий для авторов (з.111) и жанров (з.112) — страницы отличались только
// заголовком, адресом ссылки и текстом пустого состояния, всё остальное
// было копипастом.
//
// ⚠ Считается по ОБЩЕМУ каталогу, а не по полке спрашивающего: раздел
// отвечает на вопрос «что есть в библиотеке» (решение Ксении 03.08).
import { Link } from "react-router-dom";
import { booksLabel } from "../lib/plural";
import "../styles/catalog.css";

function CatalogList({ title, items, hrefBase, isLoading, isError, errorText, emptyText }) {
  return (
    <div className="catalog-list-page">
      <Link className="btn-ghost" to="/">
        ← К библиотеке
      </Link>

      <header className="catalog-list-head">
        <h1 className="title">{title}</h1>
        {items.length > 0 && <p className="muted">Всего: {items.length}</p>}
      </header>

      {isLoading && <p className="muted">Загрузка…</p>}
      {isError && <p className="error">{errorText}</p>}

      {!isLoading && !isError && items.length === 0 && (
        <p className="muted">{emptyText}</p>
      )}

      {items.length > 0 && (
        <ul className="catalog-list">
          {items.map((item) => (
            <li key={item.id}>
              <Link className="catalog-item" to={`${hrefBase}/${item.id}`}>
                <span className="catalog-item-name">{item.name}</span>
                <span className="catalog-item-count">{booksLabel(item.books)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default CatalogList;
