// Шапка страницы цикла: название, автор, прогресс, переключатель статуса.
// Вынесено из SeriesPage (R4, 26.07).
//
// В режиме правки название редактируется прямо здесь — оно самое заметное поле,
// и переносить его в форму слева было бы странно.
const STATUSES = [
  { id: "reading", label: "Читаю" },
  { id: "read", label: "Прочитан" },
  { id: "dropped", label: "Перестала читать" },
];

function SeriesHeader({ series, editing, form, onFormChange, onStatus, statusPending }) {
  const { progress } = series;

  return (
    <header className="series-header">
      <div className="series-header-text">
        {editing ? (
          <input
            className="series-title-input"
            value={form.name}
            onChange={(e) => onFormChange({ ...form, name: e.target.value })}
            placeholder="Название цикла"
          />
        ) : (
          <h1 className="series-title">{series.name}</h1>
        )}
        {!editing && series.author && (
          <p className="series-author">{series.author}</p>
        )}
        <p className="series-progress">
          Прочитано {progress.read} из {progress.total}
          {progress.on_shelf < progress.total && (
            <> · на полке {progress.on_shelf}</>
          )}
        </p>
      </div>

      {/* статус цикла — личное действие, доступно всем (з.90а) */}
      <div className="series-status-row" role="group" aria-label="Статус цикла">
        {STATUSES.map((s) => (
          <button
            key={s.id}
            className={"pill " + (series.status === s.id ? "pill-active" : "")}
            onClick={() => onStatus(s.id)}
            disabled={statusPending}
            aria-pressed={series.status === s.id}
          >
            {s.label}
          </button>
        ))}
      </div>
    </header>
  );
}

export default SeriesHeader;
