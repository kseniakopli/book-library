// Статус чтения, личная оценка, дата прочтения и внешний рейтинг Google.
// Вынесено из BookDetail (ревью 19.07). Изменения уходят наверх через onChange.
import { STATUS_LABELS, STATUSES } from "../constants";

const RATINGS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

/** ISO-дата из ответа → «2026-07-01» для <input type="date">. */
function dateValue(iso) {
  return iso ? iso.slice(0, 10) : "";
}

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

      {/* Задача 115: дата прочтения правится здесь, рядом со статусом и оценкой.
          ⚠ Это ЛИЧНОЕ действие, не admin: дата лежит в `userbook`, а модалка
          правки книги закрыта админом, потому что правит ОБЩИЕ поля каталога.
          Положить дату туда значило бы, что тестер не исправит собственную дату.
          Пустое поле разрешено намеренно: «прочитана, но не помню когда» —
          честное состояние (задача 98), и вернуться к нему тоже надо уметь. */}
      {book.status === "read" && (
        <div className="rating-row">
          <label className="rating-label" htmlFor="read-at-input">
            Прочитана:
          </label>
          <input
            id="read-at-input"
            type="date"
            value={dateValue(book.read_at)}
            onChange={(e) =>
              onChange({ read_at: e.target.value ? e.target.value : null })
            }
            disabled={saving}
          />
          {!book.read_at && <span className="muted">дата неизвестна</span>}
        </div>
      )}
    </>
  );
}

export default BookStatusRow;
