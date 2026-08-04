// Левая колонка страницы цикла: экслибрис, название, прогресс, статус,
// описание и форма правки. Вынесено из SeriesPage (R4, 26.07).
//
// Экслибрис и описание живут вместе не случайно: символ рисуется ИМЕННО
// по описанию, поэтому кнопка генерации и текст должны быть рядом — иначе
// непонятно, почему без описания символ выходит пустым.
//
// ⚠ Задача 119: сюда влился бывший `SeriesHeader` (название, автор,
// прогресс, статусы). Раньше он был шапкой НАД колонками, и цикл этим
// отличался от книги и автора, где сведения о сущности целиком слева.
// Отдельный компонент из четырёх строк, вызываемый в одном месте, себя
// не окупал — файл удалён.
//
// Порядок повторяет страницу книги: сначала образ (символ ↔ обложка),
// затем название и автор, затем личные действия (статус ↔ статус чтения),
// затем текст.
import { useMemo } from "react";
import { centeredSvgDataUri } from "../lib/svg";

const STATUSES = [
  { id: "reading", label: "Читаю" },
  { id: "read", label: "Прочитан" },
  { id: "dropped", label: "Перестала читать" },
];

function SeriesAside({
  series,
  isAdmin,
  editing,
  form,
  onFormChange,
  onStartEdit,
  onCancelEdit,
  onSave,
  savePending,
  onStatus,
  statusPending,
  onGenerateDesign,
  designPending,
  designError,
}) {
  // символ приходит SVG-строкой в паспорте цикла — рендерим как у книг
  const symbolUri = useMemo(
    () =>
      series.design?.symbol_svg
        ? centeredSvgDataUri(series.design.symbol_svg)
        : null,
    [series.design?.symbol_svg],
  );

  const { progress } = series;

  return (
    <>
      <div className="series-symbol-large" aria-hidden="true">
        {symbolUri ? (
          <img src={symbolUri} alt="" />
        ) : (
          <span className="series-symbol-empty">◆</span>
        )}
      </div>

      {/* В режиме правки название редактируется прямо на своём месте:
          оно самое заметное поле, и уводить его в форму ниже странно. */}
      {editing ? (
        <input
          className="entity-title-input"
          value={form.name}
          onChange={(e) => onFormChange({ ...form, name: e.target.value })}
          placeholder="Название цикла"
          aria-label="Название цикла"
        />
      ) : (
        <h1 className="entity-title">{series.name}</h1>
      )}
      {!editing && series.author && (
        <p className="entity-subtitle">{series.author}</p>
      )}

      <p className="muted entity-meta">
        Прочитано {progress.read} из {progress.total}
        {progress.on_shelf < progress.total && (
          <> · на полке {progress.on_shelf}</>
        )}
      </p>

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

      {/* этап 9 (хвост з.90): экслибрис цикла — общие данные, только админ */}
      {isAdmin && (
        <button
          className="btn-ghost entity-aside-btn"
          onClick={onGenerateDesign}
          disabled={designPending}
          title={
            series.description
              ? undefined
              : "Сначала добавьте описание цикла — символ рисуется по нему"
          }
        >
          {designPending
            ? "Рисую символ…"
            : series.design
              ? "Обновить экслибрис"
              : "Сгенерировать экслибрис"}
        </button>
      )}
      {designError && <p className="error">Не вышло: {designError.message}</p>}
      {series.design?.statement && (
        <p className="entity-statement">{series.design.statement}</p>
      )}

      {editing ? (
        <form
          className="entity-edit"
          onSubmit={(e) => {
            e.preventDefault();
            if (form.name.trim()) onSave();
          }}
        >
          <input
            value={form.author}
            onChange={(e) => onFormChange({ ...form, author: e.target.value })}
            placeholder="Автор"
            aria-label="Автор цикла"
          />
          <textarea
            rows={6}
            value={form.description}
            onChange={(e) =>
              onFormChange({ ...form, description: e.target.value })
            }
            placeholder="О чём цикл: мир, эпоха, что объединяет книги. По этому описанию рисуется экслибрис."
            aria-label="Описание цикла"
          />
          <div className="entity-edit-actions">
            <button className="add-btn" type="submit" disabled={savePending}>
              {savePending ? "Сохраняю…" : "Сохранить"}
            </button>
            <button className="btn-ghost" type="button" onClick={onCancelEdit}>
              Отмена
            </button>
          </div>
        </form>
      ) : (
        <>
          {series.description ? (
            <p className="entity-text">{series.description}</p>
          ) : (
            <p className="muted">
              Описания пока нет. Оно нужно, чтобы экслибрис получился осмысленным.
            </p>
          )}
          {isAdmin && (
            <button
              className="btn-ghost entity-aside-btn"
              onClick={onStartEdit}
            >
              Редактировать
            </button>
          )}
        </>
      )}
    </>
  );
}

export default SeriesAside;
