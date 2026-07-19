// Верхний ряд действий на странице книги. Вынесено из BookDetail (ревью 19.07).
import { Link } from "react-router-dom";

function BookActionsBar({
  bookId,
  onBack,
  onEnrich,
  enriching,
  onEdit,
  onDelete,
  deleting,
}) {
  return (
    <div className="detail-bar">
      <button className="btn-ghost" onClick={onBack}>
        ← К библиотеке
      </button>
      <div className="detail-bar-actions">
        <button className="btn-ghost" onClick={onEnrich} disabled={enriching}>
          {enriching ? "Обновляю…" : "Обновить информацию"}
        </button>
        <button className="btn-ghost" onClick={onEdit}>
          Редактировать
        </button>
        <Link className="btn-ghost playlist-link" to={`/books/${bookId}/evening`}>
          ☾ Начать вечер
        </Link>
        <Link className="btn-ghost playlist-link" to={`/books/${bookId}/card`}>
          Печатная карточка
        </Link>
        <button className="btn-danger" onClick={onDelete} disabled={deleting}>
          {deleting ? "Удаляю…" : "Удалить"}
        </button>
      </div>
    </div>
  );
}

export default BookActionsBar;
