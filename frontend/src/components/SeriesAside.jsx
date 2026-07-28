// Левая колонка страницы цикла: экслибрис, его генерация, описание и форма
// правки. Вынесено из SeriesPage (R4, 26.07).
//
// Экслибрис и описание живут вместе не случайно: символ рисуется ИМЕННО
// по описанию, поэтому кнопка генерации и текст должны быть рядом — иначе
// непонятно, почему без описания символ выходит пустым.
import { useMemo } from "react";
import { centeredSvgDataUri } from "../lib/svg";

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

  return (
    <aside className="series-aside">
      <div className="series-symbol-large" aria-hidden="true">
        {symbolUri ? (
          <img src={symbolUri} alt="" />
        ) : (
          <span className="series-symbol-empty">◆</span>
        )}
      </div>

      {/* этап 9 (хвост з.90): экслибрис цикла — общие данные, только админ */}
      {isAdmin && (
        <button
          className="btn-ghost series-design-btn"
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
        <p className="series-statement">{series.design.statement}</p>
      )}

      {editing ? (
        <form
          className="series-edit"
          onSubmit={(e) => {
            e.preventDefault();
            if (form.name.trim()) onSave();
          }}
        >
          <input
            value={form.author}
            onChange={(e) => onFormChange({ ...form, author: e.target.value })}
            placeholder="Автор"
          />
          <textarea
            rows={6}
            value={form.description}
            onChange={(e) =>
              onFormChange({ ...form, description: e.target.value })
            }
            placeholder="О чём цикл: мир, эпоха, что объединяет книги. По этому описанию рисуется экслибрис."
          />
          <div className="series-edit-actions">
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
            <p className="series-description">{series.description}</p>
          ) : (
            <p className="muted">
              Описания пока нет. Оно нужно, чтобы экслибрис получился осмысленным.
            </p>
          )}
          {isAdmin && (
            <button className="btn-ghost series-edit-btn" onClick={onStartEdit}>
              Редактировать
            </button>
          )}
        </>
      )}
    </aside>
  );
}

export default SeriesAside;
