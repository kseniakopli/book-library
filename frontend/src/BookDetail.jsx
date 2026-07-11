import { useEffect, useState } from "react";

const STATUS_LABELS = {
  want: "Хочу прочитать",
  reading: "Читаю",
  read: "Прочитана",
};

const STATUSES = ["want", "reading", "read"];

function BookDetail({ book, onBack, onUpdated }) {
  const [saving, setSaving] = useState(false);

  const [selections, setSelections] = useState([]);
  const [activeSource, setActiveSource] = useState("Claude");
  const [generating, setGenerating] = useState(false);

  // Подгружаем уже сохранённые подборки при открытии карточки
  useEffect(() => {
    fetch(`/books/${book.id}/music`)
      .then((r) => r.json())
      .then((data) => setSelections(data.selections));
  }, [book.id]);

  async function patch(body) {
    setSaving(true);
    const response = await fetch(`/books/${book.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const updated = await response.json();
    setSaving(false);
    onUpdated(updated);
  }

  async function generateMusic() {
    setGenerating(true);
    const response = await fetch(`/books/${book.id}/music`, { method: "POST" });
    const data = await response.json();
    setSelections(data.selections);
    setGenerating(false);
  }

  const active = selections.find((s) => s.source === activeSource);

  return (
    <div className="detail">
      <button className="btn-ghost" onClick={onBack}>← К библиотеке</button>

      <div className="detail-top">
        <div className="detail-cover">
          {book.cover_url ? (
            <img src={book.cover_url} alt={book.title} />
          ) : (
            <div className="cover-empty">Нет обложки</div>
          )}
        </div>

        <div className="detail-info">
          <h1 className="detail-title">{book.title}</h1>
          <p className="detail-author">{book.author}</p>

          <div className="status-row">
            {STATUSES.map((s) => (
              <button
                key={s}
                className={"pill " + (book.status === s ? "pill-active" : "")}
                onClick={() => patch({ status: s })}
                disabled={saving}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>

          {book.status === "read" && (
            <div className="rating-row">
              <span className="rating-label">Оценка:</span>
              <select
                value={book.rating ?? ""}
                onChange={(e) => patch({ rating: Number(e.target.value) })}
                disabled={saving}
              >
                <option value="" disabled>—</option>
                {[1,2,3,4,5,6,7,8,9,10].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {book.description && <p className="detail-description">{book.description}</p>}

      <section className="atmosphere">
        <div className="atmosphere-head">
          <h2 className="atmosphere-title">Атмосфера · Музыка</h2>
          <button className="add-btn" onClick={generateMusic} disabled={generating}>
            {generating ? "Подбираю…" : selections.length ? "Обновить" : "Подобрать музыку"}
          </button>
        </div>

        {generating && <p className="muted">Claude и ChatGPT подбирают музыку…</p>}

        {!generating && selections.length === 0 && (
          <p className="muted">Пока нет подборки. Нажмите «Подобрать музыку».</p>
        )}

        {selections.length > 0 && (
          <>
            <div className="source-tabs">
              {selections.map((s) => (
                <button
                  key={s.source}
                  className={"pill " + (activeSource === s.source ? "pill-active" : "")}
                  onClick={() => setActiveSource(s.source)}
                >
                  {s.source}
                </button>
              ))}
            </div>

            {active && (
              <>
                <p className="atmosphere-explanation">{active.explanation}</p>
                <ol className="songs">
                  {active.songs.map((song, i) => (
                    <li className="song" key={i}>
                      <span className="song-title">{song.title}</span>
                      <span className="song-artist">{song.artist}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

export default BookDetail;