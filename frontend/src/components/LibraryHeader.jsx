import { Link } from "react-router-dom";

// Шапка главной: заголовок и действия (вид полки, тема, импорт, добавить).
// Вынесено из HomePage (ревью 19.07).
//
// На этапе 9 вид полки, импорт и язык переедут в личный кабинет — тогда этот
// компонент похудеет до заголовка и кнопки «Добавить книгу».
function LibraryHeader({
  compact,
  symbolMode,
  onToggleMode,
  theme,
  onToggleTheme,
  csv,
  onAddBook,
  addButtonRef,
}) {
  return (
    <header className={"header" + (compact ? " header-compact" : "")}>
      <div>
        <h1 className="title">Библиотека</h1>
        <p className="subtitle">Атмосферные литературные вечера</p>
      </div>

      <div className="header-actions">
        <Link className="btn-ghost" to="/stats" title="Статистика чтения">
          ◔ Статистика
        </Link>

        <button
          className="btn-ghost"
          onClick={onToggleMode}
          title="Как показывать полку"
          aria-label={`Вид полки: ${symbolMode ? "символы" : "обложки"}. Переключить`}
        >
          {symbolMode ? "◈ Символы" : "▦ Обложки"}
        </button>

        <button
          className="btn-ghost theme-toggle"
          onClick={onToggleTheme}
          aria-pressed={theme === "dark"}
          aria-label={
            theme === "dark" ? "Включить светлую тему" : "Включить вечернюю тему"
          }
          title={theme === "dark" ? "Светлая тема" : "Вечерняя тема"}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>

        <input
          type="file"
          accept=".csv"
          ref={csv.inputRef}
          onChange={csv.onFileChange}
          className="file-input-hidden"
          aria-label="Файл CSV для импорта"
        />
        <button className="btn-ghost" onClick={csv.trigger} disabled={csv.importing}>
          {csv.importing ? "Импортирую…" : "Импорт CSV"}
        </button>

        <button className="add-btn" onClick={onAddBook} ref={addButtonRef}>
          + Добавить книгу
        </button>
      </div>
    </header>
  );
}

export default LibraryHeader;
