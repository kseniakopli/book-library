// Задача 65: «Вечер с книгой» — полноэкранная атмосферная сцена.
// Одна прокручиваемая сцена: герой (палитра + символ + название) → музыка →
// угощения → ароматы. Один AI-источник с переключателем (по умолчанию Claude).
// Данные переиспользуются из кэша (те же ключи, что у страницы книги) —
// бэкенд не трогаем.
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { useTheme } from "../hooks/useTheme";
import { centeredSvgDataUri } from "../lib/svg";
import { bestTextOn, withAlpha } from "../lib/contrast";

const SOURCES = ["Claude", "ChatGPT"];

function EveningPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [source, setSource] = useState("Claude");

  const exit = () => navigate(`/books/${id}`);

  // Esc закрывает сцену
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && exit();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const book = useQuery({ queryKey: keys.book(id), queryFn: () => api.getBook(id) });
  const design = useQuery({
    queryKey: keys.atmosphere(id, "design"),
    queryFn: () => api.getAtmosphere(id, "design"),
  });
  const music = useQuery({
    queryKey: keys.atmosphere(id, "music"),
    queryFn: () => api.getAtmosphere(id, "music"),
  });
  const food = useQuery({
    queryKey: keys.atmosphere(id, "food"),
    queryFn: () => api.getAtmosphere(id, "food"),
  });
  const aroma = useQuery({
    queryKey: keys.atmosphere(id, "aroma"),
    queryFn: () => api.getAtmosphere(id, "aroma"),
  });

  const passport = design.data?.selections?.[0]?.payload ?? null;
  const palette = passport
    ? theme === "dark"
      ? (passport.palette_dark ?? passport.palette)
      : (passport.palette_light ?? passport.palette_dark ?? passport.palette)
    : null;

  const symbolUri = useMemo(
    () => (passport?.symbol_svg ? centeredSvgDataUri(passport.symbol_svg) : null),
    [passport?.symbol_svg],
  );

  // Подключаем шрифты паспорта (как на странице книги)
  useEffect(() => {
    if (!passport?.title_font) return;
    const families = [passport.title_font, passport.body_font]
      .filter(Boolean)
      .map((f) => f.trim().replace(/ /g, "+"))
      .join("&family=");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${families}&display=swap`;
    document.head.appendChild(link);
    return () => document.head.removeChild(link);
  }, [passport?.title_font, passport?.body_font]);

  // выбранный источник в категории
  const pick = (q) =>
    q.data?.selections?.find((s) => s.source === source)?.payload ?? null;
  const songs = pick(music);
  const treats = pick(food);
  const scents = pick(aroma);
  const hasAny = songs || treats || scents;

  const loading =
    book.isLoading || music.isLoading || food.isLoading || aroma.isLoading;

  // Палитра → CSS-переменные сцены (или базовая тема, если паспорта нет)
  const style = palette
    ? {
        "--ev-bg": palette.bg,
        "--ev-surface": palette.surface,
        "--ev-text": palette.text,
        "--ev-muted": palette.muted,
        "--ev-accent": palette.accent,
        "--ev-on-accent": bestTextOn(palette.accent),
        "--ev-border": withAlpha(palette.muted, "44"),
        "--ev-serif": passport.title_font
          ? `'${passport.title_font}', Georgia, serif`
          : "var(--serif)",
        "--ev-sans": passport.body_font
          ? `'${passport.body_font}', system-ui, sans-serif`
          : "var(--sans)",
      }
    : {};

  return (
    <div className="evening" style={style}>
      <div className="evening-bar">
        <button className="evening-close" onClick={exit} aria-label="Закрыть вечер">
          ← К книге
        </button>
        {hasAny && (
          <div className="evening-sources" role="group" aria-label="Источник подборки">
            {SOURCES.map((s) => (
              <button
                key={s}
                className={"evening-pill" + (source === s ? " active" : "")}
                onClick={() => setSource(s)}
                aria-pressed={source === s}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <p className="evening-hint">Готовим сцену…</p>
      ) : (
        <div className="evening-scene">
          <header className="evening-hero">
            {symbolUri && (
              <img className="evening-symbol" src={symbolUri} alt="" aria-hidden="true" />
            )}
            <h1 className="evening-title">{book.data?.title}</h1>
            <p className="evening-author">{book.data?.author}</p>
            {passport?.statement && (
              <p className="evening-statement">{passport.statement}</p>
            )}
          </header>

          {!hasAny ? (
            <p className="evening-hint">
              Для вечера сначала подберите атмосферу на странице книги — музыку,
              угощения и ароматы.
            </p>
          ) : (
            <div className="evening-sections">
              {songs && (
                <section className="evening-block">
                  <h2>Музыка вечера</h2>
                  <ol className="evening-tracks">
                    {songs.map((s, i) => (
                      <li key={i}>
                        <span className="evening-track-title">{s.title}</span>
                        <span className="evening-track-artist">{s.artist}</span>
                      </li>
                    ))}
                  </ol>
                  {book.data?.spotify_playlist_url && (
                    <a
                      className="evening-play"
                      href={book.data.spotify_playlist_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      ♫ Открыть плейлист в Spotify
                    </a>
                  )}
                </section>
              )}

              {treats && (
                <section className="evening-block">
                  <h2>Угощения</h2>
                  <ul className="evening-items">
                    {treats.map((it, i) => (
                      <li key={i}>
                        <span className="evening-item-title">{it.title}</span>
                        <span className="evening-item-desc">{it.description}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {scents && (
                <section className="evening-block">
                  <h2>Ароматы</h2>
                  <ul className="evening-items">
                    {scents.map((it, i) => (
                      <li key={i}>
                        <span className="evening-item-title">{it.title}</span>
                        <span className="evening-item-desc">{it.description}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default EveningPage;
