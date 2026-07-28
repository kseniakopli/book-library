// Публичная витрина (задача 30): отобранные книги владельца — страница,
// на которую ведут QR печатных карточек.
//
// Открывается БЕЗ входа, поэтому здесь нет ни useAuth, ни запросов к закрытому
// API: только /public/{slug}. Гость видит книги и их оформление; оценки, статусы
// и даты чтения сюда не приходят вовсе (см. routers/public.py).
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { centeredSvgDataUri } from "../lib/svg";
import { pickPalette } from "../lib/palette";
import { useTheme } from "../hooks/useTheme";
import "../styles/showcase.css";

function ShowcaseCard({ slug, book, theme }) {
  const design = book.design;
  // палитра по теме — единое правило (lib/palette.js), аудит 28.07
  const palette = pickPalette(design, theme);
  const symbol = design?.symbol_svg ? centeredSvgDataUri(design.symbol_svg) : null;

  return (
    <li className="showcase-item">
      <Link className="showcase-card" to={`/u/${slug}/books/${book.id}`}>
        <span
          className="showcase-cover"
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

function ShowcasePage() {
  const { slug } = useParams();
  const { theme } = useTheme();
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.showcase(slug),
    queryFn: () => api.getShowcase(slug),
    retry: false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Такой витрины нет.</p>;

  return (
    <main className="showcase">
      <header className="showcase-head">
        <h1 className="showcase-heading">{data.title}</h1>
        {data.intro && <p className="showcase-intro">{data.intro}</p>}
      </header>

      {data.books.length === 0 ? (
        <p className="muted">Пока здесь пусто.</p>
      ) : (
        <ul className="showcase-grid">
          {data.books.map((book) => (
            <ShowcaseCard key={book.id} slug={slug} book={book} theme={theme} />
          ))}
        </ul>
      )}

      {/* витрина — рекламная страница: гость должен понять, что это за сервис */}
      <footer className="showcase-foot">
        <p className="muted">
          nocturne — вечер вокруг книги: музыка, угощения и ароматы под её
          настроение.
        </p>
      </footer>
    </main>
  );
}

export default ShowcasePage;
