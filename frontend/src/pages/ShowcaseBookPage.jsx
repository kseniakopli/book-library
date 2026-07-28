// Страница книги в публичной витрине (задача 30). Открывается без входа.
//
// Это «лицо» сервиса: гость видит книгу в её собственной палитре, символ,
// музыку, угощения и ароматы. Выбора между Claude и ChatGPT здесь нет —
// бэкенд отдаёт один вариант: посетителю наша внутренняя кухня ни о чём.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { centeredSvgDataUri } from "../lib/svg";
import "../styles/showcase.css";

const SECTIONS = [
  { id: "music", title: "Музыка" },
  { id: "food", title: "Угощения" },
  { id: "aroma", title: "Ароматы" },
];

function Section({ id, title, block }) {
  if (!block?.items?.length) return null;
  return (
    <section className="showcase-section">
      <h2 className="showcase-section-title">{title}</h2>
      {block.explanation && (
        <p className="showcase-explanation">{block.explanation}</p>
      )}
      <ul className="showcase-list">
        {block.items.map((item, i) => (
          <li key={i}>
            <span className="showcase-item-title">{item.title}</span>
            {/* музыка: исполнитель; еда и ароматы: описание */}
            <span className="showcase-item-note">
              {id === "music" ? item.artist : item.description}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ShowcaseBookPage() {
  const { slug, id } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: keys.showcaseBook(slug, id),
    queryFn: () => api.getShowcaseBook(slug, id),
    retry: false,
  });

  if (isLoading) return <p className="muted">Загрузка…</p>;
  if (isError) return <p className="error">Книга не найдена.</p>;

  // страница окрашивается палитрой книги — тот же приём, что на «Вечере»
  const palette = data.design?.palette_light || data.design?.palette_dark;
  const symbol = data.design?.symbol_svg
    ? centeredSvgDataUri(data.design.symbol_svg)
    : null;
  const themed = palette
    ? {
        background: palette.bg,
        color: palette.text,
        "--showcase-accent": palette.accent,
        "--showcase-muted": palette.muted,
      }
    : undefined;

  return (
    <main className="showcase showcase-book" style={themed}>
      <Link className="btn-ghost showcase-back" to={`/u/${slug}`}>
        ← {data.showcase_title}
      </Link>

      <header className="showcase-book-head">
        {symbol && (
          <img className="showcase-symbol" src={symbol} alt="" aria-hidden="true" />
        )}
        <div>
          <h1 className="showcase-heading">{data.title}</h1>
          <p className="showcase-author">
            {data.author}
            {data.published_year ? ` · ${data.published_year}` : ""}
          </p>
        </div>
      </header>

      {data.design?.statement && (
        <p className="showcase-statement">{data.design.statement}</p>
      )}
      {data.description && (
        <p className="showcase-description">{data.description}</p>
      )}

      {data.spotify_playlist_url && (
        <a
          className="btn-ghost"
          href={data.spotify_playlist_url}
          target="_blank"
          rel="noreferrer"
        >
          ♫ Слушать плейлист в Spotify
        </a>
      )}

      {SECTIONS.map((s) => (
        <Section key={s.id} id={s.id} title={s.title} block={data.atmosphere[s.id]} />
      ))}
    </main>
  );
}

export default ShowcaseBookPage;
