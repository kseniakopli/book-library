// Статус чтения, личная оценка и внешний рейтинг Google.
// Вынесено из BookDetail (ревью 19.07). Изменения уходят наверх через onChange.
import { STATUS_LABELS, STATUSES } from "../constants";

const RATINGS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

function BookStatusRow({ book, onChange, saving }) {
  const showRatingRow = book.status === "read" || book.external_rating != null;

  return (
    <>
      <div className="status-row" role="group" aria-label="Статус чтения">
        {STATUSES.map((s) => (
          <button
            key={s}
            className={"pill " + (book.status === s ? "pill-active" : "")}
            onClick={() => onChange({ status: s })}
            disabled={saving}
            aria-pressed={book.status === s}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {showRatingRow && (
        <div className="rating-row">
          {book.status === "read" && (
            <>
              <label className="rating-label" htmlFor="rating-select">
                Оценка:
              </label>
              <select
                id="rating-select"
                value={book.rating ?? ""}
                onChange={(e) => onChange({ rating: Number(e.target.value) })}
                disabled={saving}
              >
                <option value="" disabled>
                  —
                </option>
                {RATINGS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </>
          )}
          {book.external_rating != null && (
            // задачи 45/50: информационный бейдж, не кликабельный контрол
            <span
              className="rating-badge"
              title="Средний рейтинг Google Books (шкала 1–5)"
            >
              ★ {String(book.external_rating.toFixed(1)).replace(".", ",")} · Google
            </span>
          )}
        </div>
      )}
    </>
  );
}

export default BookStatusRow;
