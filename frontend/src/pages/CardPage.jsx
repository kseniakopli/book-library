// Печатная карточка книги (этап 10.4), макет «Медальон» (вариант 1).
// Тексты редактируются прямо на превью (contentEditable) — правки попадают
// в печать/PDF. Кнопка печати открывает диалог браузера: там «Сохранить как PDF»
// или двусторонняя печать (A6, поля «Нет», переворот по короткому краю).
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as api from "../api";
import { keys } from "../queryKeys";
import { svgDataUri } from "../lib/svg";
import "../styles/card.css";

const DEFAULT_PALETTE = {
  bg: "#171310",
  surface: "#221c17",
  accent: "#e08b2d",
  text: "#e9e1d3",
  muted: "#a19585",
};

function dedupeSongs(songs) {
  const seen = new Set();
  return songs.filter((s) => {
    const key = `${s.artist.trim().toLowerCase()}|${s.title.trim().toLowerCase()}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function useAtmosphere(id, category) {
  return useQuery({
    queryKey: keys.atmosphere(id, category),
    queryFn: () => api.getAtmosphere(id, category),
  });
}

function CardPage() {
  const { id } = useParams();
  const { data: book } = useQuery({
    queryKey: keys.book(id),
    queryFn: () => api.getBook(id),
  });
  const design =
    useAtmosphere(id, "design").data?.selections?.[0]?.payload ?? null;
  const music = useAtmosphere(id, "music").data?.selections ?? [];
  const food = useAtmosphere(id, "food").data?.selections ?? [];
  const aroma = useAtmosphere(id, "aroma").data?.selections ?? [];

  // Шрифты паспорта (Google Fonts) — как в BookDetail
  useEffect(() => {
    if (!design) return;
    const families = [design.title_font, design.body_font]
      .map((f) => f.trim().replace(/ /g, "+"))
      .join("&family=");
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${families}&display=swap`;
    document.head.appendChild(link);
    return () => document.head.removeChild(link);
  }, [design]);

  if (!book) return <p className="muted">Загрузка…</p>;

  // Треки: объединённый список обоих AI (как в Spotify-плейлисте), первые 5
  const songs = dedupeSongs(music.flatMap((s) => s.payload)).slice(0, 5);
  // Угощения/ароматы: подборка Claude (или первая доступная)
  const pick = (sel) =>
    (sel.find((s) => s.source === "Claude") ?? sel[0])?.payload ?? [];
  const foods = pick(food).slice(0, 4);
  const aromas = pick(aroma).slice(0, 3);

  let genres = "";
  try {
    genres = (JSON.parse(book.categories) ?? []).slice(0, 2).join(" · ");
  } catch {
    genres = "";
  }

  const p = design?.palette ?? DEFAULT_PALETTE;
  const style = {
    "--c-bg": p.bg,
    "--c-surface": p.surface,
    "--c-accent": p.accent,
    "--c-text": p.text,
    "--c-muted": p.muted,
    "--c-serif": design
      ? `'${design.title_font}', Georgia, serif`
      : "Georgia, serif",
    "--c-sans": design
      ? `'${design.body_font}', system-ui, sans-serif`
      : "system-ui, sans-serif",
  };

  const ready = songs.length > 0 && foods.length > 0 && aromas.length > 0;

  return (
    <div className="card-page" style={style}>
      <div className="card-controls">
        <Link className="btn-ghost" to={`/books/${id}`}>
          ← К книге
        </Link>
        {!ready && (
          <p className="error">
            Для полной карточки нужны атмосфера (музыка, угощения, ароматы)
            {book.spotify_playlist_url ? "" : " и Spotify-плейлист"} — вернитесь
            на страницу книги и сгенерируйте недостающее.
          </p>
        )}
        <p className="muted">
          Кликните любой текст на карточке, чтобы поправить его перед печатью.
        </p>
        <button className="add-btn" onClick={() => window.print()}>
          Печать / сохранить PDF
        </button>
        <p className="muted">
          В диалоге печати: бумага A6, поля — «Нет», масштаб 100%, двусторонняя
          печать — переворот по короткому краю.
        </p>
      </div>

      {/* ======== ЛИЦО ======== */}
      <div className="pcard">
        <div className="pc-symbol-plate">
          {design?.symbol_svg && (
            <img src={svgDataUri(design.symbol_svg)} alt="" />
          )}
        </div>
        <h1 className="pc-title" contentEditable suppressContentEditableWarning>
          {book.title}
        </h1>
        <p className="pc-author" contentEditable suppressContentEditableWarning>
          {book.author}
        </p>
        <p className="pc-meta" contentEditable suppressContentEditableWarning>
          {genres}
          {genres && book.external_rating != null && " · "}
          {book.external_rating != null &&
            `★ ${String(book.external_rating.toFixed(1)).replace(".", ",")} · Google`}
        </p>
        {/* Statement на карточку не выводим (решение 16.07): длинная цитата
            вытесняла треки — приоритет у «Музыки вечера» */}
        <div className="pc-tracks">
          <h4>Музыка вечера</h4>
          <div contentEditable suppressContentEditableWarning>
            {songs.map((s, i) => (
              <div className="pc-track" key={i}>
                <span>{s.title}</span>
                <span>{s.artist}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="pc-qr-row">
          {book.spotify_playlist_url ? (
            <img
              className="pc-qr"
              src={`/books/${id}/qr`}
              alt="QR-код плейлиста в Spotify"
            />
          ) : (
            <div className="pc-qr pc-qr-empty">нет плейлиста</div>
          )}
          <p className="pc-qr-hint" contentEditable suppressContentEditableWarning>
            Полный плейлист к этой книге — в Spotify
          </p>
        </div>
      </div>

      {/* ======== ОБОРОТ ======== */}
      <div className="pcard pc-back">
        <h2 className="pc-back-title" contentEditable suppressContentEditableWarning>
          Вечер с этой книгой
        </h2>
        <h4>Угощения</h4>
        <div contentEditable suppressContentEditableWarning>
          {foods.map((f, i) => (
            <div className="pc-item" key={i}>
              <b>{f.title}</b>
              <br />
              <span>{f.description}</span>
            </div>
          ))}
        </div>
        <h4>Ароматы</h4>
        <div contentEditable suppressContentEditableWarning>
          {aromas.map((a, i) => (
            <div className="pc-item" key={i}>
              <b>{a.title}</b> — <span>{a.description}</span>
            </div>
          ))}
        </div>
        <div className="pc-footer">
          {design?.symbol_svg && (
            <img src={svgDataUri(design.symbol_svg)} alt="" />
          )}
          <span contentEditable suppressContentEditableWarning>
            <b>Nocturne</b> — атмосферные литературные вечера.
            <br />
            Собрано AI под эту книгу · связь: kseniakopli@gmail.com
          </span>
        </div>
      </div>
    </div>
  );
}

export default CardPage;
