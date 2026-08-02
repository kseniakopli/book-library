import { Link } from "react-router-dom";
import { useAuth, useLogout } from "../hooks/useAuth";

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
  const { user, isAdmin } = useAuth();
  const logout = useLogout();

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
          {/* стрелки парные (↑ загрузить / ↓ выгрузить) — иначе соседние
              кнопки об одном и том же выглядят разнородными */}
          {csv.importing ? "Импортирую…" : "↑ Импорт CSV"}
        </button>

        {/* Задача 35: выгрузка полки. Обычная ссылка, а не fetch — браузер сам
            приложит куку сессии и сам сохранит файл по Content-Disposition,
            без Blob и URL.createObjectURL.
            ⚠ В задаче 110 и эта кнопка, и «Импорт CSV» уедут в меню ЛК —
            шапка уже переполнена, здесь она временно. */}
        <a
          className="btn-ghost"
          href="/api/v1/export/shelf.csv"
          download
          title="Скачать свою полку в CSV"
        >
          ↓ Экспорт
        </a>

        <button className="add-btn" onClick={onAddBook} ref={addButtonRef}>
          + Добавить книгу
        </button>

        {/* Этап 9: кто вошёл и выход. Аватар из Google — просто картинка
            по ссылке, ничего от нас не требует. */}
        {user && (
          <span className="user-chip" title={user.email || ""}>
            {user.avatar_url && (
              <img className="user-avatar" src={user.avatar_url} alt="" />
            )}
            <span className="user-name">
              {user.display_name}
              {isAdmin && <span className="user-role"> · админ</span>}
            </span>
            <button
              className="btn-ghost user-logout"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              title="Выйти"
            >
              Выйти
            </button>
          </span>
        )}
      </div>
    </header>
  );
}

export default LibraryHeader;
